"""CRTC bridge from canonical flip records to cross-list listing drafts.

The bridge is intentionally marketplace-neutral: it prepares one master
listing payload. Marketplace adapters remain responsible for approved API
publishing.

Flow this module implements:

    canonical flip
          v
    build_master_listing()      <- deterministic, no network, no AI
          v
    enrich_listing_with_ai()    <- optional, best-effort, never blocking
          v
    (caller: listing validation, human review/edit, marketplace draft,
     explicit publish action)

build_master_listing() must keep working exactly the same whether or not
an AI provider is configured, reachable, or healthy -- AI enrichment is an
optional decoration on top of a listing that is already valid without it.
"""

import hashlib
import json
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional


def _stable_sku(flip: Dict[str, Any]) -> str:
    """Collision-safe fallback SKU for a flip with no sku/source_listing_id.

    Never returns a constant like the old "CRTC-ITEM" fallback -- 200
    manual flips with none of their own identifiers used to all collapse
    onto that one literal string, silently overwriting each other in
    listing_store.upsert_listing()'s (sku, marketplace) keying (F-08).

    Always includes a fresh random component: two independently created
    flips can have identical item_name/cost_basis/notes (two otherwise-
    identical $5 rings from the same source, entered by hand, at the same
    moment), and must never derive the same SKU just because their
    content happens to match -- a pure content hash is not collision-safe
    under concurrent identical-looking creates. This means calling
    build_master_listing() twice for the very same flip dict produces two
    different fallback SKUs (two listing_store rows, not one updated in
    place) -- a real tradeoff, but a duplicate row a human can merge is a
    far smaller problem than two unrelated items silently sharing one
    identity. The flip's own content is still hashed in alongside the
    nonce so the result isn't a bare random string.
    """
    payload = {
        "item_name": flip.get("item_name"),
        "cost_basis": flip.get("cost_basis"),
        "source": flip.get("source"),
        "notes": flip.get("notes"),
        "created_at": flip.get("created_at"),
        "id": flip.get("id"),
        "_nonce": uuid.uuid4().hex,
    }
    raw = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    digest = hashlib.sha256(raw).hexdigest()[:12].upper()
    return f"CRTC-{digest}"


def build_master_listing(flip: Dict[str, Any]) -> Dict[str, Any]:
    """Create a cross-list-ready master listing from a tracked flip.

    "image_urls" is the one canonical field name for photo URLs across
    this app's whole listing pipeline (flip record -> master listing ->
    marketplace draft): ebay_sell.py's master_to_inventory_item() already
    reads master["image_urls"] directly, and pages/5_Cross_List.py's
    production-publish payload construction reads draft["image_urls"] the
    same way -- previously this field was written here as "photos",
    which NEITHER of those two ever read, so every eBay listing (sandbox
    or production) published through this pipeline went out with zero
    images regardless of what a flip had. Never rename this field again
    without checking both those call sites."""
    status = str(flip.get("status") or "").upper()
    if status not in {"PURCHASED", "LISTED"}:
        raise ValueError("Only PURCHASED or LISTED flips can enter listing workflow")
    title = str(flip.get("item_name") or "Untitled item").strip()
    if not title:
        raise ValueError("A listing title is required")
    list_price = float(flip.get("list_price") or 0)
    if list_price <= 0:
        raise ValueError("A positive list price is required before listing")
    return {
        "sku": str(flip.get("sku") or flip.get("source_listing_id") or _stable_sku(flip)),
        "title": title,
        "description": str(flip.get("description") or flip.get("notes") or ""),
        "category": str(flip.get("category") or ""),
        "price": round(list_price, 2),
        "cost": round(float(flip.get("cost_basis") or 0), 2),
        "quantity": int(flip.get("quantity") or 1),
        "condition": str(flip.get("condition") or "Used"),
        "image_urls": list(flip.get("image_urls") or []),
        "source": str(flip.get("source") or ""),
        "source_listing_id": str(flip.get("source_listing_id") or ""),
        "source_url": str(flip.get("source_url") or ""),
        "status": "MASTER_READY",
    }


# ---------------------------------------------------------------------------
# AI-assisted listing enrichment
# ---------------------------------------------------------------------------
# Contract, deliberately narrow: the AI may draft copy (title, description,
# highlights, keyword tags) and summarize CONDITION WORDING from evidence
# the caller supplies. It may not be the source of new facts. The
# dataclass below has no field for specifications, provenance, accessories,
# measurements, or authenticity claims -- that's the actual enforcement
# mechanism, not just a prompt instruction: even if a provider's JSON
# includes such a field, nothing in this module reads it into the result.

AI_CONFIDENCE_LEVELS = ("low", "medium", "high")

# Stripe-style "fail closed on size, not on provider" bound: reject an
# oversized request before ever making a network call, rather than
# truncating silently and drafting copy from a chopped-off description.
MAX_INPUT_CHARS = 8000

_ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
_ANTHROPIC_MODEL = "claude-sonnet-5"
_DEFAULT_TIMEOUT_SECONDS = 30

_SYSTEM_PROMPT = (
    "You draft resale marketplace listing copy for a human seller who will "
    "review and edit everything before publishing. You are given a master "
    "listing (title, category, price, condition) and an 'evidence' object "
    "containing ONLY facts the seller has actually supplied (condition "
    "notes, measurements, accessories, provenance notes, photo "
    "descriptions). Do not state any specification, measurement, "
    "accessory, provenance, or authenticity claim that is not present in "
    "the evidence or the master listing itself. If a detail a buyer would "
    "normally want is not present in the evidence, list it in "
    "missing_information instead of guessing. Respond with ONLY valid "
    "JSON, no other text, no markdown fences, using exactly these fields: "
    "title (string), description (string), highlights (array of short "
    "strings), condition_summary (string, based only on supplied "
    "evidence), missing_information (array of strings), confidence (one "
    "of: low, medium, high)."
)

_RESULT_FIELDS = (
    "title",
    "description",
    "highlights",
    "condition_summary",
    "missing_information",
)


@dataclass
class ListingAIResult:
    """Structured result of one AI enrichment attempt. Never raises --
    callers check `success`; on failure every text/list field is empty and
    the master listing built by build_master_listing() remains the
    authoritative, publishable record."""

    success: bool = False
    title: str = ""
    description: str = ""
    highlights: List[str] = field(default_factory=list)
    condition_summary: str = ""
    missing_information: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    confidence: str = ""
    provider: str = "anthropic"
    model: str = ""
    error: str = ""


class _HTTPError(Exception):
    def __init__(self, status_code: int, body: str = ""):
        super().__init__(f"HTTP {status_code}")
        self.status_code = status_code
        self.body = body


def _default_transport(url: str, headers: Dict[str, str], body: bytes, timeout: int) -> bytes:
    """Real network transport, isolated behind a swappable function so
    tests never make a real HTTP call. Mirrors the existing
    urllib-based Anthropic call already used elsewhere in this app (no new
    dependency needed for this module)."""
    import urllib.error
    import urllib.request

    req = urllib.request.Request(url, data=body, method="POST")
    for key, value in headers.items():
        req.add_header(key, value)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read()
    except urllib.error.HTTPError as e:
        raise _HTTPError(e.code, e.read().decode("utf-8", "replace")) from e
    except TimeoutError as e:
        raise TimeoutError(str(e)) from e


def _bounded(text: Any, limit: int = 2000) -> str:
    text = "" if text is None else str(text)
    return text[:limit]


def _build_evidence_payload(evidence: Optional[Dict[str, Any]]) -> Dict[str, str]:
    evidence = evidence or {}
    allowed_keys = (
        "condition_notes",
        "measurements",
        "accessories_included",
        "provenance_notes",
        "photos_described",
    )
    return {key: _bounded(evidence.get(key, "")) for key in allowed_keys if evidence.get(key)}


def _total_input_size(master_listing: Dict[str, Any], evidence: Optional[Dict[str, Any]]) -> int:
    """Size check against the RAW input, before any per-field truncation --
    otherwise a single oversized field would just get silently cut down to
    size instead of the request being rejected outright."""
    listing_text = "".join(str(master_listing.get(k, "")) for k in ("title", "description", "category"))
    evidence_text = "".join(str(v) for v in (evidence or {}).values())
    return len(listing_text) + len(evidence_text)


def _validate_ai_payload(raw: Dict[str, Any]) -> ListingAIResult:
    """Extracts only whitelisted fields from a parsed AI JSON response.
    Any field outside the contract (an invented 'authenticity' or
    'specifications' key, for example) is silently dropped here -- it
    never reaches ListingAIResult, regardless of what the provider sent."""
    warnings: List[str] = []

    title = _bounded(raw.get("title", ""), 200)
    description = _bounded(raw.get("description", ""), 4000)
    condition_summary = _bounded(raw.get("condition_summary", ""), 1000)

    highlights_raw = raw.get("highlights", [])
    highlights = [_bounded(h, 200) for h in highlights_raw if isinstance(h, (str, int, float))] \
        if isinstance(highlights_raw, list) else []
    if not isinstance(highlights_raw, list):
        warnings.append("AI response 'highlights' was not a list; ignored.")

    missing_raw = raw.get("missing_information", [])
    missing_information = [_bounded(m, 200) for m in missing_raw if isinstance(m, (str, int, float))] \
        if isinstance(missing_raw, list) else []
    if not isinstance(missing_raw, list):
        warnings.append("AI response 'missing_information' was not a list; ignored.")

    confidence = str(raw.get("confidence", "")).lower().strip()
    if confidence not in AI_CONFIDENCE_LEVELS:
        if confidence:
            warnings.append(f"AI returned an unrecognized confidence level ({confidence!r}); defaulted to 'low'.")
        confidence = "low"

    if not title and not description:
        warnings.append("AI response contained no usable title or description.")

    return ListingAIResult(
        success=True,
        title=title,
        description=description,
        highlights=highlights,
        condition_summary=condition_summary,
        missing_information=missing_information,
        warnings=warnings,
        confidence=confidence,
        provider="anthropic",
        model=_ANTHROPIC_MODEL,
    )


def enrich_listing_with_ai(
    master_listing: Dict[str, Any],
    evidence: Optional[Dict[str, Any]] = None,
    *,
    api_key: Optional[str] = None,
    timeout: int = _DEFAULT_TIMEOUT_SECONDS,
    max_input_chars: int = MAX_INPUT_CHARS,
    transport: Optional[Callable[[str, Dict[str, str], bytes, int], bytes]] = None,
) -> ListingAIResult:
    """Best-effort AI enrichment of a master listing built by
    build_master_listing(). Never raises: any failure (missing key,
    timeout, auth, rate limit, malformed response) returns a
    ListingAIResult with success=False and a human-readable `error`, and
    the caller's listing workflow should proceed unchanged using the
    deterministic master_listing fields.

    `evidence` should contain only facts the user actually supplied
    (condition_notes, measurements, accessories_included,
    provenance_notes, photos_described) -- this is deliberately not the
    full flip record, so nothing the AI wasn't given can leak into its
    "based on the evidence" framing.
    """
    transport = transport or _default_transport

    if not api_key:
        return ListingAIResult(success=False, error="AI provider not configured (missing API key).")

    if _total_input_size(master_listing, evidence) > max_input_chars:
        return ListingAIResult(
            success=False,
            error=f"Input too large for AI enrichment (limit {max_input_chars} characters).",
        )

    evidence_payload = _build_evidence_payload(evidence)

    user_payload = {
        "master_listing": {
            "title": _bounded(master_listing.get("title", "")),
            "category": _bounded(master_listing.get("category", "")),
            "price": master_listing.get("price"),
            "condition": _bounded(master_listing.get("condition", "")),
            "description": _bounded(master_listing.get("description", "")),
        },
        "evidence": evidence_payload,
    }
    if not evidence_payload:
        user_payload["note"] = "No evidence was supplied. Populate missing_information accordingly."

    try:
        body = json.dumps({
            "model": _ANTHROPIC_MODEL,
            "max_tokens": 900,
            "system": _SYSTEM_PROMPT,
            "messages": [{"role": "user", "content": json.dumps(user_payload)}],
        }).encode("utf-8")
        headers = {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        raw_response = transport(_ANTHROPIC_URL, headers, body, timeout)
    except _HTTPError as e:
        if e.status_code == 401:
            return ListingAIResult(success=False, error="AI provider authentication failed.")
        if e.status_code == 429:
            return ListingAIResult(success=False, error="AI provider rate limit exceeded.")
        return ListingAIResult(success=False, error=f"AI provider returned an error (HTTP {e.status_code}).")
    except TimeoutError:
        return ListingAIResult(success=False, error="AI provider request timed out.")
    except Exception as e:
        return ListingAIResult(success=False, error=f"AI provider request failed: {e}")

    try:
        envelope = json.loads(raw_response)
    except (json.JSONDecodeError, TypeError, UnicodeDecodeError):
        return ListingAIResult(success=False, error="AI provider response was not valid JSON.")

    content_blocks = envelope.get("content", []) if isinstance(envelope, dict) else []
    raw_text = "".join(
        block.get("text", "") for block in content_blocks
        if isinstance(block, dict) and block.get("type") == "text"
    ).strip()

    if not raw_text:
        return ListingAIResult(success=False, error="AI provider returned an empty response.")

    try:
        parsed = json.loads(raw_text)
    except json.JSONDecodeError:
        return ListingAIResult(success=False, error="AI response content was not valid JSON.")

    if not isinstance(parsed, dict):
        return ListingAIResult(success=False, error="AI response JSON was not an object.")

    return _validate_ai_payload(parsed)
