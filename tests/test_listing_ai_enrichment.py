"""Unit tests for listing_bridge.py's AI enrichment abstraction.

Covers the contract required for production: a normal listing must build
successfully via build_master_listing() with or without AI, and every
provider failure mode (auth, rate limit, timeout, malformed/empty/non-JSON
response, oversized input, unsupported claims) must degrade to a
ListingAIResult(success=False, ...) rather than raising or fabricating
data.
"""

import json

import pytest

from listing_bridge import (
    AI_CONFIDENCE_LEVELS,
    MAX_INPUT_CHARS,
    ListingAIResult,
    build_master_listing,
    enrich_listing_with_ai,
)

MASTER_LISTING = {
    "title": "Vintage Camera",
    "category": "Electronics",
    "price": 199.0,
    "condition": "Used",
    "description": "",
}


def _anthropic_envelope(text: str) -> bytes:
    return json.dumps({"content": [{"type": "text", "text": text}]}).encode("utf-8")


def _transport_returning(text: str):
    def transport(url, headers, body, timeout):
        return _anthropic_envelope(text)
    return transport


def _transport_raising(exc):
    def transport(url, headers, body, timeout):
        raise exc
    return transport


class TestNormalListingWithoutAI:
    def test_master_listing_builds_without_calling_ai_at_all(self):
        flip = {"status": "PURCHASED", "item_name": "Camera", "list_price": 100}
        result = build_master_listing(flip)
        assert result["status"] == "MASTER_READY"

    def test_enrich_without_api_key_fails_closed_without_network_call(self):
        called = {"n": 0}

        def transport(*a, **k):
            called["n"] += 1
            return _anthropic_envelope("{}")

        result = enrich_listing_with_ai(MASTER_LISTING, api_key=None, transport=transport)
        assert result.success is False
        assert "not configured" in result.error.lower()
        assert called["n"] == 0

    def test_master_listing_remains_valid_when_ai_result_is_discarded(self):
        # The caller can always ignore enrich_listing_with_ai() entirely and
        # publish master_listing fields as-is.
        flip = {"status": "LISTED", "item_name": "Ring", "list_price": 50}
        master = build_master_listing(flip)
        assert master["title"] == "Ring"
        assert master["price"] == 50.0


class TestValidResponse:
    def test_valid_ai_response_populates_result(self):
        payload = {
            "title": "Vintage 35mm Film Camera",
            "description": "A used film camera, tested and working.",
            "highlights": ["Tested working", "Includes strap"],
            "condition_summary": "Light wear consistent with age.",
            "missing_information": ["Original box"],
            "confidence": "medium",
        }
        transport = _transport_returning(json.dumps(payload))
        result = enrich_listing_with_ai(
            MASTER_LISTING,
            evidence={"condition_notes": "tested and working"},
            api_key="sk-ant-test",
            transport=transport,
        )
        assert result.success is True
        assert result.title == "Vintage 35mm Film Camera"
        assert result.highlights == ["Tested working", "Includes strap"]
        assert result.confidence == "medium"
        assert result.provider == "anthropic"


class TestMalformedResponse:
    def test_malformed_fields_do_not_crash_and_default_safely(self):
        payload = {
            "title": "OK Title",
            "description": "OK description",
            "highlights": "not a list",
            "missing_information": 12345,
            "confidence": "extremely-sure",
        }
        transport = _transport_returning(json.dumps(payload))
        result = enrich_listing_with_ai(MASTER_LISTING, api_key="k", transport=transport)
        assert result.success is True
        assert result.highlights == []
        assert result.missing_information == []
        assert result.confidence == "low"
        assert any("highlights" in w for w in result.warnings)
        assert any("confidence" in w for w in result.warnings)


class TestProviderTimeout:
    def test_timeout_returns_failed_result(self):
        transport = _transport_raising(TimeoutError("timed out"))
        result = enrich_listing_with_ai(MASTER_LISTING, api_key="k", transport=transport)
        assert result.success is False
        assert "timed out" in result.error.lower()


class TestProviderAuthFailure:
    def test_401_returns_failed_result(self):
        from listing_bridge import _HTTPError

        transport = _transport_raising(_HTTPError(401, "unauthorized"))
        result = enrich_listing_with_ai(MASTER_LISTING, api_key="bad-key", transport=transport)
        assert result.success is False
        assert "authentication" in result.error.lower()


class TestProviderRateLimit:
    def test_429_returns_failed_result(self):
        from listing_bridge import _HTTPError

        transport = _transport_raising(_HTTPError(429, "slow down"))
        result = enrich_listing_with_ai(MASTER_LISTING, api_key="k", transport=transport)
        assert result.success is False
        assert "rate limit" in result.error.lower()


class TestOversizedInput:
    def test_oversized_evidence_is_rejected_before_any_network_call(self):
        called = {"n": 0}

        def transport(*a, **k):
            called["n"] += 1
            return _anthropic_envelope("{}")

        huge_evidence = {"condition_notes": "x" * (MAX_INPUT_CHARS + 1)}
        result = enrich_listing_with_ai(MASTER_LISTING, evidence=huge_evidence, api_key="k", transport=transport)
        assert result.success is False
        assert "too large" in result.error.lower()
        assert called["n"] == 0


class TestMissingItemFacts:
    def test_empty_evidence_still_calls_ai_and_preserves_missing_information(self):
        payload = {
            "title": "Untitled Vintage Item",
            "description": "Condition and specifics unknown; seller has not supplied details.",
            "highlights": [],
            "missing_information": ["condition", "measurements", "accessories"],
            "confidence": "low",
        }
        transport = _transport_returning(json.dumps(payload))
        result = enrich_listing_with_ai(MASTER_LISTING, evidence={}, api_key="k", transport=transport)
        assert result.success is True
        assert "condition" in result.missing_information


class TestUnsupportedClaims:
    def test_fields_outside_the_contract_are_dropped_not_surfaced(self):
        # A provider that ignores instructions and invents extra claims
        # (authenticity, provenance, specifications) must not have those
        # claims reach the caller -- the dataclass simply has no field for
        # them, so they're structurally unreachable regardless of prompt
        # compliance.
        payload = {
            "title": "Sterling Silver Ring",
            "description": "A ring.",
            "highlights": [],
            "missing_information": [],
            "confidence": "high",
            "authenticity_certified": True,
            "provenance": "owned by a famous collector",
            "specifications": {"purity": "999 fine silver"},
        }
        transport = _transport_returning(json.dumps(payload))
        result = enrich_listing_with_ai(MASTER_LISTING, api_key="k", transport=transport)
        assert not hasattr(result, "authenticity_certified")
        assert not hasattr(result, "provenance")
        assert not hasattr(result, "specifications")
        assert "authenticity_certified" not in vars(result)


class TestEmptyResponse:
    def test_empty_text_returns_failed_result(self):
        transport = _transport_returning("")
        result = enrich_listing_with_ai(MASTER_LISTING, api_key="k", transport=transport)
        assert result.success is False
        assert "empty" in result.error.lower()


class TestNonJsonResponse:
    def test_non_json_text_returns_failed_result(self):
        transport = _transport_returning("Sure! Here's a great listing for your item:")
        result = enrich_listing_with_ai(MASTER_LISTING, api_key="k", transport=transport)
        assert result.success is False
        assert "json" in result.error.lower()

    def test_non_json_envelope_returns_failed_result(self):
        def transport(url, headers, body, timeout):
            return b"not json at all"

        result = enrich_listing_with_ai(MASTER_LISTING, api_key="k", transport=transport)
        assert result.success is False


class TestAIUnavailableEndToEnd:
    def test_full_listing_lifecycle_works_with_ai_completely_unavailable(self):
        flip = {
            "status": "PURCHASED",
            "item_name": "Estate Sale Lamp",
            "source": "HiBid",
            "source_listing_id": "H99",
            "cost_basis": 20,
            "list_price": 65,
        }
        master = build_master_listing(flip)
        ai_result = enrich_listing_with_ai(master, api_key="")
        assert master["status"] == "MASTER_READY"
        assert ai_result.success is False
        assert master["title"] == "Estate Sale Lamp"


def test_confidence_levels_constant_matches_validation():
    assert AI_CONFIDENCE_LEVELS == ("low", "medium", "high")


def test_listing_ai_result_defaults_are_all_empty_and_unsuccessful():
    result = ListingAIResult()
    assert result.success is False
    assert result.title == ""
    assert result.highlights == []
    assert result.missing_information == []
