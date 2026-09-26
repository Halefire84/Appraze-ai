# AI Analyzer vision spec — Android photo walk-through

Status: **SPEC ONLY. Not built.** Per Chris's direction, this is blocked on an Anthropic API
key + billing decision he hasn't made yet, and building without keys would just be
speculative code nobody can run or verify. This document is detailed enough to build from
once that's unblocked, without re-deriving the design decisions below.

## Product direction (Chris, 2026-09-26 — do not re-derive, this is settled)

The "Goodwill walk-through" flow: a reseller stands in front of an item with their phone.

- **Cost (purchase/hammer price) stays a manual input.** The user already knows what they'd
  pay — that's not something a photo can tell you.
- **Expected resale is auto-filled by AI from the photo(s).** The user never types a resale
  number for this flow.
- **Minimal flow:** snap picture(s) (+ optional free text) + enter cost → AI identifies the
  item and returns a market value → the existing deal math runs → verdict.
- Multiple photos allowed per item.
- A vision-capable AI API, called from a secure backend. **API keys never live on the
  device** — same rule as Stripe (see `docs/POS_STRIPE_CONNECT.md`) and eBay
  (`docs/COMPS_POLLER.md`).

This is the same shape as the comps collector already shipped for typed descriptions
(`CompsLookup.java` / `comps_collector.py`): describe the item → auto-fill Expected resale →
show the evidence behind the number → let the verdict note where resale came from. The vision
flow is that same pattern, triggered by a photo instead of typed text. Where this doc doesn't
say otherwise, **match `CompsLookup`'s conventions** rather than inventing new ones.

## What already exists — reuse, don't rewrite

1. **`app.py`'s AI Analyzer tab (~line 1147 onward)** is the reference implementation for
   talking to Anthropic: an Anthropic Messages API call with an image content block, a system
   prompt that demands a strict JSON response (`itemName`, `category`, `conditionEstimate`,
   `estimatedValueLow`, `estimatedValueHigh`, `confidence`, `reasoning`, plus listing-draft
   fields the mobile MVP doesn't need), `claude-sonnet-5`, and $2/$10 per Mtok cost accounting.
   The mobile backend's prompt and JSON contract should be **the same fields** (minus the
   listing drafts) so both surfaces stay consistent and one prompt gets tuned, not two.
2. **`ai_usage.py`** is the existing cost/quota-control model for the web app: reserve before
   calling the provider, finalize with actual token counts after, release on failure, a
   15-minute stale-reservation expiry, per-day and per-month caps. It's Apps-Script-backed
   (keyed by a logged-in username), which the mobile backend can't reuse directly since the
   Android app has no server-verified accounts yet (`Usage.java`'s own comment: "everyone is
   free until backend verification lands" — a known, already-flagged gap, not new). The
   mobile version needs the same reserve/finalize/release *shape*, backed by SQLite and a
   device identity instead (see below) — not a rewrite of the policy, a new store for it.
3. **`ebay_image_scan.py`** (`search_ebay_by_image()`) already exists, is tested, and is
   **not currently wired into any UI** (see `AI_NOTES.md`). It calls eBay's own
   `search_by_image` Browse endpoint — same eBay app credentials the mobile backend already
   has — and returns ordinary `comps.Comp` objects (`listing_type=ACTIVE`) for visually
   similar active listings. It does not identify the item, but it is a second, independent,
   **already-built, no-new-keys** signal for "what's this worth" that costs an eBay call, not
   an Anthropic call. Use it as a cross-check on Claude's own value guess (see "Two evidence
   sources" below) and as the fallback when Anthropic isn't configured or a device is out of
   AI quota for the day — "AI item-ID unavailable" should not have to mean "no value estimate
   at all."
4. **`comps.py`'s `summarize_comps()`** — reused unchanged, exactly like `comps_collector.py`
   and `comps_poller.py` already do. `ebay_image_scan.py`'s comps feed straight into it.
5. **The device-token pattern in `pos_connect.py`** (issue a random token, store only its
   sha256 server-side, let the device revoke it) is the right shape for AI-usage device
   identity too — see below — but it is a **different token for a different purpose**. Do
   not reuse the Stripe Connect token for this: a free user with no Stripe account still uses
   Analyze, and a device's AI quota has nothing to do with its POS connection state.

## Two evidence sources, not one — and never let the AI alone decide BUY

This app's stated principle, right in `app.py`'s own AI Analyzer caption: **"Your own profit
math (not the AI) still decides buy/pass — review everything before saving."** The vision
spec keeps that principle, and goes one step further: it doesn't even let Claude's raw value
guess stand alone as "the" market value when a second, independently-verifiable source is
available.

| Source | What it gives | Cost | Trust |
|---|---|---|---|
| Claude vision (Anthropic) | item ID, category, condition, a value range, reasoning | ~$0.01-0.05/call (est., see cost accounting below) | An LLM's estimate — useful, not verified |
| eBay image search (`ebay_image_scan.py`) | real, currently-active comparable listings | one eBay Browse call, already-budgeted infra | Real listings, but active/asking-price only (same honesty rule `comps.py` already enforces — see `docs/COMPS_POLLER.md`) |

**Combination rule (mirrors `CompsLookup`'s existing confidence display, not a new concept):**
- If eBay image search returns usable comps, run them through `comps.summarize_comps()` and
  show **both** numbers: "Claude's estimate: $X-Y" and "Similar listings on eBay: $Z (n
  listings)". Auto-fill Expected resale from the eBay comps median when available (real
  listings > an LLM guess, same evidence-first ordering `comps.py` already uses for sold vs.
  active), falling back to the midpoint of Claude's range only when no usable eBay comps
  come back.
- If Claude vision fails or isn't configured, but eBay image search works, auto-fill from
  eBay image comps alone (labeled as such, confidence per `comps.py`'s existing "active
  listings only" rule) and skip the item-ID/condition fields (show "describe it yourself"
  instead — same graceful-degradation pattern as `comps_collector.py`'s "not configured" path).
- If both fail, same as today: manual resale entry, no crash, no dialog you can't dismiss.
- **Never silently pick a number when both sources disagree wildly** (say, >2x apart) —
  surface both, let the human pick, exactly like showing "verify before you buy" on low
  confidence in the existing `CompsLookup` card. Do not average them into a false-precision
  single figure.

## Backend design (new module, e.g. `vision_analyzer.py`, mounted the same way as
`pos_connect.py` / `comps_collector.py` / `comps_poller.py` on `stripe_webhook_server.py`)

### Device identity for AI usage metering

Not the Stripe Connect token. A separate, lightweight device token, same shape as
`pos_connect.TokenStore` (random token, sha256 stored, revocable):

- `POST /vision/device/register` — no auth, rate-limited per IP (mirror
  `comps_collector.py`'s per-IP/day limits) — issues a device token. No business address, no
  Stripe account, nothing sensitive: this only exists so per-device AI quota can't be reset by
  clearing app data and immediately re-registering at will (it *can* be reset that way today,
  same as any device-only identity — call this out to Chris as a known, honest limitation,
  not a solved problem; a real account system is the actual fix, and is explicitly out of
  scope here, matching `PlanSettings.java`'s own existing TODO).
- Be honest in the UI and in code comments that this token is a **quota key, not
  authentication** — unlike the Stripe device token (which gates access to a specific
  merchant's real money), losing or duplicating this one only costs Appraze some AI spend,
  not a customer's funds. Different risk profile, so it's fine that it's weaker; don't
  over-engineer it to look like the Stripe token's security model.

### Usage gating (mirrors `ai_usage.py`'s policy, new SQLite-backed store)

- `reserve` before calling Anthropic (atomic increment against a daily+monthly cap, same as
  `ai_usage.py`); `finalize` with actual token counts after a successful response for cost
  accounting; `release` on any failure so a dropped connection doesn't cost the user a real
  reservation. Same 15-minute stale-reservation expiry.
- Suggested starting limits, subject to Chris's call on real numbers once billing is set up:
  same order of magnitude as `ai_usage.py`'s beta policy (10/day, 100/month per device on
  Free; higher on paid plans) — do not just copy the web numbers uncritically, since mobile
  photo analysis has a different image-token cost than the web flow's already-uploaded photo.
- Reuse `ai_usage.py`'s cost formula ($2/Mtok in, $10/Mtok out) for accounting, adjusted if
  Anthropic's published rates have changed by the time this is built — don't hardcode the
  number without checking.
- Wire this into the existing `Usage.SCANS` counter client-side (Android already has this
  counter, already plumbed through `PlanSettings.upgradeDialog`, and it currently gates
  *nothing* — see `Usage.java`'s own docstring: "the current Android build has no dedicated
  scan screen, so nothing consumes it yet"). This vision flow **is** that scan screen. Gate it
  the same way `Get Verdict` and `Publish` already gate on `Usage.tryConsume(...)`, consuming
  `Usage.SCANS` instead of `Usage.ANALYSES`. The client-side counter is provisional (same
  known gap as today) — the real enforcement is the server-side reserve/finalize above, same
  relationship the app already has between client-side `Usage` and Stripe/POS's server-side
  truth.

### Endpoint

`POST /vision/analyze` (device token in `Authorization: Bearer`)

Request:
```json
{
  "images": ["<base64 jpeg/png, max 3MB each, same cap as ai_usage.py's MAX_IMAGE_BYTES>", "..."],
  "text": "optional free text, max 2000 chars (ai_usage.py's MAX_DESCRIPTION_CHARS)"
}
```

- Reject empty images+text (400), over-limit images (400, per-image size check like
  `ebay_image_scan.py`'s existing magic-byte + size validation — reuse that validation code,
  don't reinvent it), too many images (cap at some small N, e.g. 4 — multiple angles, not a
  photo album).
- Multiple images go into one Anthropic call as multiple image content blocks (Claude
  supports multi-image messages) — not N separate calls; that would N-x the cost per item for
  no benefit here.

Response (fields chosen to match `CompsLookup`'s existing JSON shape where the concepts
overlap, so the Android UI code is closely parallel, not reinvented):
```json
{
  "ok": true,
  "item_name": "string",
  "category": "string",
  "condition_estimate": "string",
  "ai_value_low": 0.0,
  "ai_value_high": 0.0,
  "ai_confidence": "Low|Medium|High",
  "reasoning": "string",
  "ebay_comps": { "...": "same shape comps_collector.py already returns, when available" },
  "suggested_value": 0.0,
  "suggested_value_source": "ebay_comps|ai_range_midpoint",
  "collected_at": "ISO-8601 UTC"
}
```

- 401: bad/missing device token. 429: quota/rate limit (message says which — daily device
  quota, or Anthropic itself rate-limiting). 503: Anthropic not configured (mirrors
  `comps_collector.py`'s "not configured" 503 for eBay). Never a raw provider error body to
  the client — same rule `app.py` already follows ("Do not surface provider response bodies
  to customers").
- Anthropic/eBay credentials read from server environment variables, same
  `_use_env_ebay_credentials()`-style shim `comps_collector.py`/`comps_poller.py` already use
  for eBay; a parallel `ANTHROPIC_API_KEY` env var read directly (no Streamlit secrets
  involved at all for this one, since there's no existing Streamlit-coupled AI helper to
  redirect the way `comps_adapters.py` needed for eBay).

## Android UI (extends the existing Analyze screen — `MainActivity.analyze()`,
`PhotoCapture.java`, `CompsLookup.java` already there; a new `VisionLookup.java` sibling
following `CompsLookup.java`'s file as a close a template as possible)

- The existing "Take Photo" / "Upload Photo" buttons and 96dp thumbnail (`PhotoCapture.java`,
  `analysisPhoto` field) already exist. Add: once a photo is attached, show an "Analyze Photo"
  button next to "Find Comps" (from `CompsLookup`) — same visual weight, same card.
  Multi-photo: extend `PhotoCapture`/`analysisPhoto` from a single URI to a small list (a
  scoped, additive change to that file, not a rewrite) — cap at 4, matching the backend limit.
- Tapping "Analyze Photo": same UX skeleton as `CompsLookup.addTo()` — disable the button,
  "Analyzing photo...", call the backend, then render an evidence card and auto-fill Expected
  resale. Reuse `CompsLookup`'s confidence color/label helpers (`confidenceColor`,
  `confidenceLabel`) for `ai_confidence`.
- Evidence card content: item name + category (new — comps-by-text doesn't have this),
  condition estimate, the AI's value range, its reasoning (one line, like `confidence_reason`
  today), then — if present — the eBay comps sub-section reusing `CompsLookup`'s existing
  listings rendering almost verbatim (sold/active counts, range, tappable listings, collected
  timestamp).
- The verdict banner's provenance note (`CompsLookup.provenance()`) needs a third case:
  "Resale from AI photo analysis · <confidence>" vs. today's "Resale from eBay comps
  · <confidence>" — same mechanism, one more source label.
- Backend not configured, or device out of quota: fall back exactly like `CompsLookup` does
  today when the server isn't set up — a plain message, manual resale entry still works, no
  dead end.
- Gate the button itself on `Usage.tryConsume(Usage.SCANS)` → `PlanSettings.upgradeDialog`
  on failure, same pattern as `Get Verdict`/`Publish` — **consume usage only after local
  validation** (a photo is attached), per the standing gate-ordering rule already fixed
  elsewhere in this app (`c2d933e`, "consume usage only after field validation").

## Security / cost-control checklist (do not build without these)

- [ ] `ANTHROPIC_API_KEY` server-side only, never logged, never returned to the client.
- [ ] Per-device daily/monthly reserve+finalize+release, atomic, with stale-reservation expiry.
- [ ] Per-IP + global rate limits on `/vision/device/register` (abuse of token minting itself).
- [ ] Image size/type validation reusing `ebay_image_scan.py`'s existing magic-byte checks.
- [ ] Provider error bodies never surfaced verbatim to the client.
- [ ] A hard per-request image count cap (proposed: 4).
- [ ] Marketplace/photo content is untrusted input to the LLM call: the system prompt must
      keep "identify and value this item" as the only instruction the model follows: nothing
      a photo, a scrawled note visible in it, or free-text description says should be able to
      make the model ignore its system prompt, invent a different output schema, or emit
      anything other than the fixed JSON contract. Treat photo content and any accompanying
      text exactly like marketplace listing text is already treated elsewhere in this app's
      operating rules: it is data the model reasons about, never an instruction it follows.
      Parse the response defensively (as `app.py`'s existing `try`/`except
      json.JSONDecodeError` already does) rather than trusting it can't be malformed or
      manipulated.

## Explicitly NOT in this spec (separate, later decisions)

- Auto-listing or auto-posting from the AI's output — out of scope; `app.py`'s own tab
  already establishes "review everything before saving," and this mobile flow keeps that.
- A real account/login system to make the device token a strong per-user identity — flagged
  as a known gap, not solved here.
- BYO Anthropic key per merchant — explicitly out of scope per `AI_USAGE_CONTROLS.md`
  ("BYO Anthropic keys are explicitly out of scope for the current beta"); this mobile spec
  follows the same policy, one platform-managed key.
- Which exact Anthropic model / limits / prices to launch with — a real business decision
  for Chris once he's ready to set up billing, not something to lock in speculatively here.

## Build order once unblocked (keys + billing decided)

1. Device-token store + reserve/finalize/release usage gating (new SQLite store, mirroring
   `pos_connect.TokenStore`'s pattern) — this can be built and tested with a fake Anthropic
   client before real keys exist, same as `pos_connect.py`/`comps_collector.py` were built and
   tested against fakes/stripe-mock before any live credential was available.
2. `POST /vision/analyze`, Anthropic call behind the reservation, `ebay_image_scan.py`
   wired in as the cross-check/fallback (this part needs no new keys at all — eBay
   credentials already exist server-side).
3. Android `VisionLookup.java` + `PhotoCapture` multi-image extension + Analyze screen wiring
   + `Usage.SCANS` gating.
4. Regression tests mirroring `test_pos_connect.py`/`test_comps_collector.py`'s style (fake
   provider, real `comps.summarize_comps()`), plus Android JVM tests mirroring
   `CompsLookupTest`.
5. Only then: a real Anthropic key in a sandboxed/budget-capped test, exactly like Stripe
   Connect and the comps poller were each proven against fakes first and real credentials
   last.
