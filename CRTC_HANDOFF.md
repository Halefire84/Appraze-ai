# CRTC — Project Handoff Point

**Canonical repository:** Halefire84/Appraze-ai  
**Product direction:** CRTC (Cooper River Trading Co.)  
**Last handoff:** 2026-09-18 (production-hardening pass)

## 2026-09-18 production-hardening pass
Baseline before changes: `python3 -m pytest tests/ -q` -> 251 passed, 0 failed
(pytest/streamlit/pandas/requests/fastapi/uvicorn/httpx/stripe installed
fresh into the environment first — none were present). No secrets, `eval`/
`exec`/`pickle`/`subprocess`, or missing-timeout HTTP calls were found in a
full-repo grep sweep.

Changes made, each verified by the test suite (final: `python3 -m pytest
tests/ -q` -> 291 passed, 0 failed, 0 regressions):
- **stripe_webhooks.py**: `verify_stripe_signature` now rejects a
  signature whose timestamp is more than 5 minutes (Stripe's own
  recommended tolerance) from the current time, closing a replay-attack
  gap where a captured valid payload+signature could otherwise be
  replayed indefinitely. Configurable via `tolerance_seconds`/`now` for
  callers and tests. 7 new tests in `tests/test_stripe_webhooks.py`.
- **app.py**: `static/manifest.json` was never actually linked into the
  page — `.streamlit/config.toml` claimed a "head-injection snippet" that
  did not exist, so the app was not installable as a PWA despite having a
  manifest and icons. Added a real injection via
  `st.components.v1.html()` (writes into `window.parent.document.head`,
  the only way to reach the true page `<head>` from Streamlit without a
  custom component). Known limitation: this only runs on app.py itself;
  Streamlit's multipage `pages/*.py` scripts don't re-run app.py, so a
  deep link straight to a sub-page won't carry the manifest tag. manifest
  `start_url` is `/`, i.e. app.py, so this doesn't block installability
  today but is worth revisiting if deep-link installs matter later.
- **ebay_image_scan.py**: rewritten with the full defensive-handling list
  from the hardening spec — size cap (10 MB), MIME allowlist + magic-byte
  sanity check, specific `EbayImageSearchError` for timeout/connection
  failure/HTTP 4xx&5xx/malformed JSON/expired token, result dedup, and a
  hard cap on returned result count. 17 new tests in
  `tests/test_ebay_image_scan.py`. (Not yet wired into any Streamlit page
  — was dead code before and after this pass.)
- **listing_bridge.py**: added `enrich_listing_with_ai()` +
  `ListingAIResult`, a testable AI abstraction sitting between
  `build_master_listing()` (unchanged, still fully deterministic) and the
  marketplace-draft step. No API key in source (reads from a caller-
  supplied `api_key`, matching the existing `ANTHROPIC_API_KEY`
  Streamlit-secrets pattern already used in app.py's Analyzer tab).
  Explicit timeout, hard input-size cap enforced before any network call,
  swappable `transport` for testing (no new dependency — reuses the
  urllib pattern already in app.py). The result dataclass has no field
  for specifications/provenance/accessories/measurements/authenticity, so
  even a provider that ignores its prompt instructions can't get an
  invented claim into the result — enforced structurally, not just by
  prompt wording. 17 new tests in `tests/test_listing_ai_enrichment.py`
  covering all 11 required cases (valid/malformed/empty/non-JSON
  response, timeout, auth failure, rate limit, oversized input, missing
  evidence, unsupported-claim rejection, and AI-completely-unavailable).
  **Not yet wired into any Streamlit page** — it's a ready-to-use library
  function; the Cross-List page (`pages/5_🔗_Cross_List.py`) is the
  logical place to call it next, deliberately left undone this pass
  rather than making an unverified UI change with no way to browser-test
  it in this environment.

## 2026-09-20 — Radar integration: preserve rich eBay listings through the scan
Context: a "CRTC — New Master Development Direction" doc (simulation-driven
P0–P20 hardening plan: canonical BUY decision, Stripe replay/refund/
ordering fixes, category-mismatch pipeline fix, financial-input
validation, SKU/listing-identity integrity, etc.) was handed off in the
same session as a narrower, immediately-actionable request: finish wiring
rich eBay listings through `listing_normalizer.py` into the existing
Opportunity Radar. This entry covers only that narrower request, actually
completed and tested this session. **The P0–P20 plan itself is not yet
started** — see "Unresolved issues" below; the next session should begin
there, in the stated priority order, not re-litigate prioritization.

**Discrepancy to flag**: the handoff message claimed "the only intentional
uncommitted change is comps_adapters.py, where fetch_listings() was added
to EbayBrowseAdapter." At the start of this session, `git status` showed a
clean working tree and `EbayBrowseAdapter` had no `fetch_listings` method
— that change was not present in this checkout (likely made in a
different session/machine that never pushed/synced here). Rather than
fabricate around the gap, `fetch_listings()` was implemented fresh this
session as described below.

Root cause found: `opportunity_sources.scan_ebay_active()` (dead code —
grepped, zero callers anywhere in the repo) built its Radar-bound listing
dicts from `EbayBrowseAdapter.fetch_comps()`'s `Comp` objects. `Comp` has
no `source_listing_id`/`description`/`category` field, so the dict it
rebuilt **always set `"source_listing_id": ""` and `"description": ""`
for every listing**, regardless of what eBay actually returned — every
listing scanned through this path would have collapsed onto the same
blank identifier. The primary hunt path (`ebay_holy_grail.py` ->
`holy_grail_pipeline.py`) already did this correctly and was not touched.

Fix:
- **comps_adapters.py**: added `EbayBrowseAdapter.fetch_listings()`, a
  sibling to `fetch_comps()` (not a replacement — `fetch_comps()` has a
  zero-line diff, verified with `git diff`). Calls the identical Browse
  `search` endpoint and does the same defensive price parsing, but
  returns the full per-item record (source_listing_id with the same
  itemId -> legacyItemId -> itemWebUrl fallback chain `ebay_holy_grail.py`
  already uses, url, title, description, category, condition, shipping,
  seller, location, images, auction_end) instead of a reduced `Comp`.
- **opportunity_sources.py**: `scan_ebay_active()` now calls
  `fetch_listings()` -> `listing_normalizer.normalize_listing()` ->
  `holy_grail_pipeline.rank_opportunities()`, so source_listing_id/url/
  description/category survive into the ranked `OpportunityCandidate`.
  `verdict_engine.py`/`opportunity_result.py` were not recreated (they
  stay removed per commit 7aae182); `crtc_opportunity.py`/
  `holy_grail_pipeline.py` already cover that surface.

Tests run (all real, actually executed this session):
```
python3 -m pytest tests/test_comps_adapters.py tests/test_opportunity_sources.py -q
  -> 32 passed
python3 -m pytest tests/ -q
  -> 300 passed, 0 failed, 0 errored (291 baseline + 9 new: 5 in
     test_comps_adapters.py for fetch_listings, 4 in
     test_opportunity_sources.py for the scan_ebay_active fix)
python3 -m compileall -q .
  -> exit 0, no output (all files compile)
git diff --check
  -> exit 0, no output (no whitespace/conflict-marker errors)
```
Known limitation: `fetch_listings()`'s field names for `categories`,
`shortDescription`, `itemLocation`, `seller`, and `image`/
`additionalImages` are taken from eBay's public Browse API docs, not
verified against a live call in this session (no eBay credentials
available here) — same caveat `EbayMarketplaceInsightsAdapter`'s own
docstring already carries for the same reason. `scan_ebay_active()` still
has no UI caller (unchanged from before this fix); wiring it into a page
is future work, not done here.

## 2026-09-20 — file inventory: mark dead code, correct stale docs
The user asked for an inventory of "old shit" in the repo and to either
delete or mark unused files. Built a full import graph (grepped every
root `.py` module against `app.py`, every `pages/*.py`, and `tests/`) and
cross-checked findings against `git log` per-file and the existing docs.

**Attempted `git rm` on the confirmed-dead files; the environment's
auto-mode classifier denied it as an "Irreversible Local Destruction"
action.** Used the user's explicitly offered fallback instead: marked
each file's docstring `NOT CURRENTLY USED` with the specific evidence,
rather than deleting. Files are still present and importable; nothing
was removed.

Confirmed dead (zero references from `app.py`, any `pages/*.py`, or
`tests/`), now marked in their own headers:
- `crtc.py` — a Cross-List prototype superseded by
  `pages/5_🔗_Cross_List.py`; would actually error if run standalone
  (calls `st.set_page_config()` outside the `pages/` mechanism).
- `pos.py` — superseded when `app.py` was consolidated into one
  production app. **Notable side-finding, not yet resolved:** `app.py`'s
  live "Charge Customer" tab creates a Stripe **Payment Link** (fixed
  price) inline instead of using this module's one-off Checkout Session
  approach — per this file's own docstring, a Payment Link is the wrong
  primitive for a point-of-sale charge that's a different amount every
  time. Worth revisiting: the live code may be the one that needs
  fixing, not this file that needs deleting.
- `billing.py` — only consumer was `pos.py` (also dead); `app.py` has no
  paywall/subscription-verification logic anywhere (grepped for
  "paywall", "subscription", "verify_checkout", "is_paid" — zero hits).
- `mail.py` — `README.md` claimed it "powers the Mail tab"; `app.py` has
  no Mail tab (grepped its 6 real tabs: Deal Dashboard, Profit
  Calculator, Inventory, Suppliers, Charge Customer, AI Analyzer).
- `drive_scan.py` — zero references anywhere, no test coverage.
  `README.md` described it as active; that was stale.

Kept as tested pure logic despite its only caller (`mail.py`) being dead:
`mail_parse.py` (real tests in `tests/test_mail_parse.py`, small, easy to
revive).

Explicitly NOT marked dead / NOT touched — different category from the
above (unused today, but tied to a live roadmap doc or recent deliberate
work, not superseded legacy code): `financial_intelligence.py` /
`payments_adapter.py` (scaffolding named in `CRTC_FINANCIAL_ROADMAP.md`),
`crtc_learning.py` (tested, referenced by `docs/CRTC_CONTINUOUS_HUNT.md`),
`ebay_image_scan.py` (hardened by Claude in the 2026-09-18 pass,
deliberately staged for future wiring, not legacy).

Docs corrected to stop describing dead/unused modules as live features:
- `README.md` — fixed the intro line and `app.py`'s tab list to match
  its actual 6 tabs (verified by grepping `st.tabs(...)`), split the
  module list into "wired in" vs. "built but not currently wired," and
  removed a bullet for `verdict_engine.py`, which doesn't exist in this
  repo at all (deleted in commit `7aae182`, long before this pass —
  `README.md` had never been updated to drop it).
- `AI_NOTES.md` — this is a **multi-agent coordination file**; the repo
  is also worked on by another AI (Grok) per its own text. Its "current
  state" summary was stale (162 tests when the real count is 300, the
  same nonexistent `verdict_engine.py` reference, several modules
  described as active that aren't). Corrected in place rather than
  rewritten, with an explicit note-to-self at the top: this file can go
  stale exactly like any other doc, so cross-check it against
  `git log`/`grep` rather than trusting it blindly.

Tests run: `python3 -m pytest tests/ -q` -> 300 passed, 0 failed (no
regressions — no runtime code changed, only docstrings/markdown).
`python3 -m compileall -q .` -> exit 0. `git diff --check` -> exit 0.

## Unresolved issues carried into the next session
The "CRTC — New Master Development Direction" P0 list has NOT been
started yet (no code changes in this entry address it):
1. Canonical BUY decision engine (unify the 70%-of-market-value rule and
   finance.py's 40% ROI threshold into one authority).
2. Stripe webhook replay protection — **partially done already**: see the
   2026-09-18 entry above, `verify_stripe_signature()` already has a
   5-minute timestamp-tolerance check. Signature-rotation (accept any
   valid v1 signature during rotation) and durable event-idempotency are
   still open.
3. Stripe refund accounting — `stripe_webhooks.py` still treats Stripe's
   `refunded` boolean as a monetary amount rather than reading the actual
   refunded-amount field; partial/multiple/duplicate refunds are unhandled.
4. Category-mismatch detection — `opportunity_radar.detect_category_mismatch()`
   still derives its expected-keyword evidence from the listing's own
   category/title/description (see `listing_normalizer._expected_keywords()`),
   so it can validate itself. Needs an independent taxonomy/classifier.
5. Financial input validation (NaN/Infinity/negative/boolean-as-number)
   is not yet enforced at a system boundary.
6. Unknown acquisition costs (shipping, buyer premium) are not yet
   modeled as an explicit KNOWN/UNKNOWN/ESTIMATED/NOT_APPLICABLE state —
   still capable of silently defaulting to 0 in places (e.g. `shipping=0.0`
   in `ebay_image_scan.py`'s comps, which is fine there since it's outside
   BUY-decision math, but the broader financial-normalization layer the
   direction doc asks for does not exist yet).
7. Buyer-premium unit ambiguity (`buyer_premium` vs `buyer_premium_pct`)
   not yet resolved; `listing_normalizer.NormalizedListing.buyer_premium`
   is a single ambiguous field today.
8. SKU/listing-identity collisions — `listing_bridge.build_master_listing()`
   still falls back to the literal string `"CRTC-ITEM"` when both `sku`
   and `source_listing_id` are missing, which is exactly the collision
   the direction doc flags.
9. P2 items (adversarial test matrix, observability around financial/
   payment events, mobile/Windows/web deployment review, concurrency
   review) not started.

Recommended next session: start at P0 item 1 (canonical decision engine)
per the direction doc's stated priority order, inspecting `finance.py`,
`comps.py`, `crtc_opportunity.py`, and `holy_grail_pipeline.py` first —
do not re-ask the user to reprioritize.

## Current state
- Appraze repository remains the canonical codebase; do NOT start a replacement app/repository.
- Opportunity Radar backend exists in `opportunity_radar.py`.
- Opportunity Radar tests exist in `tests/test_opportunity_radar.py`.
- Streamlit page exists at `pages/1_🔎_Opportunity_Radar.py`.
- Existing eBay Browse API adapter can retrieve active listings through the official API.
- Existing comps architecture distinguishes active asking prices from sold/completed-sale evidence.
- New `listing_normalizer.py` converts source-specific records into the common CRTC listing schema.
- New `tests/test_listing_normalizer.py` covers alias handling, metadata preservation, and batch normalization.
- New `source_registry.py` contains the expandable legitimate-source registry, with eBay currently the only automated source enabled by default.
- New `tests/test_source_registry.py` covers registry behavior and safe source onboarding.

## Product vision
CRTC is the resale opportunity-intelligence system inside the existing Appraze codebase.

Core flow:
`SOURCE → NORMALIZE → FIND ANOMALIES → VALUE → OPPORTUNITY SCORE → CRTC BUY/PASS → TRACK → LIST → SELL → MEASURE PROFIT`

Holy-grail opportunity signals include:
- spelling errors / obvious typos
- weak or incomplete titles
- title/description contradictions
- likely wrong category
- unusually low asking price versus credible market evidence
- combinations of multiple weak signals that make a listing worth human review

## Holy Grail multi-source discovery
CRTC should NOT depend on one marketplace. Build the acquisition layer as a pluggable source registry so new legitimate sources can be added without changing the Radar/scoring engine.

### Priority source groups
1. **Core resale marketplaces / auction platforms**
   - eBay
   - HiBid
   - Proxibid
   - LiveAuctioneers
   - Invaluable
   - AuctionZip / auctioneer discovery
   - Everything But The House (EBTH)
   - MaxSold
   - CTBids / Estate Auctions
   - ShopGoodwill / Goodwill auctions

2. **Government, municipal, police and institutional surplus**
   - GSA Auctions
   - GovDeals
   - Public Surplus
   - GovPlanet
   - PropertyRoom
   - Municibid
   - Purple Wave
   - state/local government surplus portals
   - police/seized-property auctions
   - school, university, airport, hospital and other institutional surplus auctions

3. **Local and regional auction houses**
   - independent online-only estate auctions
   - estate-liquidation companies
   - bankruptcy and business-liquidation auctions
   - industrial/equipment auctions
   - farm and construction auctions
   - storage-unit / abandoned-property auctions where legally accessible
   - local auctioneer catalogs and directories

4. **Specialty opportunity sources to evaluate**
   - storage/locker auction platforms
   - retail returns/liquidation marketplaces
   - commercial liquidation platforms
   - jewelry/watch/coin specialty auctions
   - vintage/collectibles specialty auctions
   - regional charity/thrift auctions

### Source discovery rule
The source list is intentionally expandable. CRTC should maintain a source registry with fields such as:
- source name
- source type/category
- geographic coverage
- acquisition method (official API, permitted feed/export, public catalog, user-provided data, etc.)
- active/sold evidence capability
- category coverage
- source URL
- rate/usage limits
- terms/compliance notes
- enabled/disabled status

CRTC should periodically identify additional legitimate auction platforms and regional sources that are likely to contain resale opportunities, then add them through adapters rather than hard-coding source-specific logic into the Radar.

Do not treat an aggregator as the authoritative source when the original auction listing is available. Preserve the original auction URL and source identity so the user can verify the lot and bid directly.

## Holy Grail detection across sources
Every source should be transformed into a common listing schema before scoring. The normalized record should preserve, when available:
- source and source listing ID
- original URL
- title
- description
- category
- asking/current bid price
- auction end time
- seller/auctioneer identity
- location and pickup/shipping information
- buyer premium and known fees
- images/image URLs when permitted
- condition
- lot number
- estimated value / market evidence

Radar should then look for the same anomaly classes across every source: typos, weak metadata, title/description contradictions, category errors, suspiciously low prices, incomplete brand/model identifiers, and combinations of weak signals. It should also learn source-specific patterns without changing the core scoring contract.

## Next implementation target
1. ~~Connect the existing eBay Browse acquisition to `listing_normalizer.py`, preserving the richer listing fields instead of reducing everything immediately to `Comp` objects.~~ **Done 2026-09-20** — see that entry above (`EbayBrowseAdapter.fetch_listings()` + `opportunity_sources.scan_ebay_active()`). The auction/last-chance path (`ebay_holy_grail.py`) already did this before.
2. ~~Feed normalized eBay records into Opportunity Radar and rank the live candidates while preserving original listing URLs.~~ **Done** — same fix; `source_listing_id`/`url`/`description`/`category` now survive into the ranked `OpportunityCandidate`. `scan_ebay_active()` still has no UI caller (pre-existing gap, not addressed).
3. **STOP — superseded by the 2026-09-20 "New Master Development Direction" P0/P1 list above.** Do not resume the numbered items below (dedicated opportunity model/UI, additional source adapters, verdict-workflow wiring) until every P0 item in that list is resolved, tested, and committed — hardening now takes priority over new source coverage or new features. See "Unresolved issues carried into the next session" above for the concrete starting point (P0 item 1: canonical decision engine).
4. Add source adapters incrementally, prioritizing CTBids/Estate Auctions, ShopGoodwill, HiBid, and other sources where legitimate acquisition is available. — deferred, see item 3.
5. Connect promising candidates to the existing valuation/comps and CRTC verdict workflow. — deferred, see item 3.

## Guardrails
- Do not build anti-bot bypasses or evasion tooling.
- Prefer official APIs, permitted feeds, exports, public catalogs where permitted, and user-supplied data.
- Respect each source's terms, robots/access controls, rate limits, authentication requirements, and licensing restrictions.
- Radar scores are leads, not proof. Authenticity, condition, sold comps, fees, shipping, pickup costs, and category must be verified before a purchase decision.
- Preserve the existing application architecture and tests.
- Avoid duplicating the valuation/verdict engines when existing modules can be reused.

## Naming direction
Use **CRTC** as the product-facing name going forward. The GitHub repository name may remain `Appraze-ai` until a deliberate repository rename is made. Do not rename files or break imports merely for branding.

## Handoff instruction
If context/usage runs out, resume from this document. First inspect the current repository state and recent commits, then continue with the numbered "Next implementation target" above. Do not rebuild prior work.
