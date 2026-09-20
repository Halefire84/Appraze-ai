# CRTC — Project Handoff Point

**Canonical repository:** Halefire84/Appraze-ai  
**Product direction:** CRTC (Cooper River Trading Co.)  
**Last handoff:** 2026-09-20 (P0 hardening: canonical decision engine + webhook correctness)

## OPEN PRODUCT REQUIREMENTS (owner-requested 2026-09-20, not started — check this before closing out any "done" milestone)

1. **Pluggable payment processor — not Stripe-only.** Owner wants the POS
   "Charge Customer" flow to eventually support more than one merchant
   processor, not lock the business owner into Stripe specifically.
   `payments_adapter.py` already has provider-neutral scaffolding for this
   (`PaymentEvent` dataclass) but nothing implements a second processor
   yet. Scope realistically: pick one concrete second processor (Square
   is the natural fit for in-person card POS) and build a real adapter
   behind that interface — don't attempt a generic "any merchant" layer,
   every processor's API shape is genuinely different.
2. **Bring-your-own Anthropic API key.** Owner wants a business owner to
   optionally supply their own `ANTHROPIC_API_KEY` for the AI
   Analyzer/listing-enrichment features instead of relying on the shared
   platform key. Blocked on architecture today: this is a single shared
   Streamlit deployment (one global key), not multi-tenant. Two options,
   different sizes of lift:
   - Lighter: a per-session override field in the app UI, stored via the
     existing Apps-Script-backed table (per-login, not truly multi-tenant
     secrets).
   - Heavier: real multi-tenant secret storage — a bigger architecture
     change, see "Multi-tenant data isolation" under known limitations
     below, which is already an open item for unrelated reasons.
   Hard constraint either way: every AI feature must keep failing safe
   with zero API calls when no key is configured (already true for
   `enrich_listing_with_ai()` and the AI Analyzer — preserve this), and
   nothing should call the API speculatively when a deterministic path
   already answers the question.

## 2026-09-20 (later) — P0 hardening: canonical decision engine, webhook correctness, SKU/category fixes

### Where this came from
Two things converged this session: a "New Master Development Direction" doc
(a simulation campaign against this codebase found 4 High/5 Medium/7 Low/1
Info findings, F-01 through F-17) and a separately uploaded
`CRTC-P0-hardened.zip` — real work from a parallel ChatGPT/Codex session
(see `CHATGPT_HANDOFF.md`/`CRTC_SESSION_PROMPTS.md`) that had already built
`decision_policy.py`, `number_normalize.py`, and `tests/test_p0_regression.py`
against an OLDER snapshot of this repo (it predated this session's PWA fix
and the `pos.py` Charge Customer wiring above). Neither session had
visibility into the other's work. This entry is the reconciliation: the
new modules were pulled in, the parts of `stripe_webhooks.py` and
`listing_bridge.py` that had diverged were merged (keeping both sides'
real fixes), and — since the zip's own plan explicitly called for it but
never did it — `auction_radar.py` and `crtc_opportunity.py` were
additionally migrated to the canonical engine, which the zip had not
touched.

### 1. Canonical decision engine (`decision_policy.py`) — NEW
Single source of truth for BUY/PASS/REVIEW, replacing three independent,
occasionally-disagreeing copies of the "70% of market value" rule that
previously lived in `deal_workspace.py`, `auction_radar.py`, and
`crtc_opportunity.py`.

```
Acquisition rule:  all-in cost <= 70% of estimated market value
ROI tiers (after known fees, via finance.calc_deal/five_tier_verdict):
  STRONG BUY  >= 60%
  BUY         >= 40%
  AT CEILING  >= 20%
  BORDERLINE  >= 5%
  PASS        < 5%
```
A workspace-style acquisition "BUY" at exactly the 70% limit typically
yields ~24% ROI after a 13% resale fee — that's `AT CEILING` on the ROI
scale, not `BUY`. `evaluate_deal()` returns BOTH the acquisition decision
and the ROI tier explicitly (`DealDecision.decision` and `.roi_tier_label`)
and adds a `warnings` entry when they disagree, rather than picking one
number and hiding the other. Cost states are explicit
(`KNOWN`/`UNKNOWN`/`ESTIMATED`/`NOT_APPLICABLE`); a material unknown cost
(auction buyer premium, required shipping) returns `REVIEW` or
`CONDITIONAL BUY` with the missing assumption named — it is never
silently treated as `$0`. Invalid numbers (NaN/Inf/negative) return
`REVIEW`, never `BUY`/`STRONG BUY`.

Wired in:
- `deal_workspace.build_deal_workspace()` — now a one-line delegate to
  `decision_policy.build_deal_workspace_record()`.
- `crtc_opportunity.build_opportunity()` — delegates via
  `evaluate_deal(is_auction=False, require_shipping=False)`; explicit
  `decision`/`max_buy_price`/`reason` override params still work exactly
  as before (backward compatible for any caller that passes them).
- `auction_radar.enrich_auction_opportunities()` — delegates via
  `evaluate_deal(is_auction=True, require_shipping=True)`; the
  `meta["acquisition_cost"]` dict shape `pages/2_🏷️_Auction_Hunt.py` reads
  (`.get("all_in_cost")`) is preserved exactly, rebuilt from
  `decision.cost_components` rather than the old `calculate_auction_cost()`.
- `finance.calc_deal()` additionally hardened directly (NaN/Inf/negative
  inputs now return a safe PASS `DealResult` instead of propagating
  garbage) as defense-in-depth for any caller that reaches it without
  going through `decision_policy` first.

**Not migrated, deliberately:** `acquisition_hunter.py`'s
`estimate_max_bid()`/`score_acquisition()` (used by the bulk-liquidation
`pages/2_📦_Liquidation_Surplus.py` workflow) and `crtc_hunt_engine.py`'s
composite Radar+acquisition tier score. Both use a genuinely different
model (recovery-rate-adjusted margin math for salvage lots, and a 0–100
lead-quality score for "how promising is this to investigate") — not
another copy of the single-item 70%/ROI rule. Forcing these through
`decision_policy.evaluate_deal()` would be a category error, not a fix.

### 2. `number_normalize.py` — NEW
Canonical parser distinguishing dollars vs. percentage points vs.
fractional percentages: `parse_money("$1,234.50")`, `parse_percent_points("18%")`
/ `parse_percent_points(0.18)` (both → `18.0`), `parse_number(...)`. Wired
into `auction_costs.calculate_auction_cost()` and
`auction_costs.max_bid_for_target_all_in()` — both used to do a bare
`float(buyer_premium_pct)` cast, which would silently treat a `0.18`
fraction as `0.18%` (a 100x unit error) instead of `18%`.
`buyer_premium`/`buyer_premium_pct` are percentage points everywhere in
this codebase now; `buyer_premium_amount` is the dollar figure.

### 3. Stripe webhook correctness (`stripe_webhooks.py`, `AppsScript_Code.gs`, `webhook_store.py`)
Merged the zip's more complete rewrite with this session's earlier
replay-protection work (both had independently built a timestamp
tolerance check):
- **Refund accounting was wrong** — `handle_charge_refunded()` used to
  read Stripe's `refunded` field, which is a **boolean** ("was this
  charge ever refunded at all," true even for a $0.01 partial refund),
  and divided it by 100 as if it were a dollar amount. Now reads the
  actual `amount_refunded` field and distinguishes `"Refunded"` (full)
  from `"Partially Refunded"`.
- **Signature rotation** — `verify_stripe_signature()` now accepts ANY
  matching `v1=` value in the header, not just one; Stripe sends multiple
  during a signing-secret rotation window.
- **Non-ASCII / malformed headers** — raise a controlled
  `StripeWebhookError`, never an unhandled exception.
- **Stale timestamp is now a raise, not a `False`** — `verify_stripe_signature()`
  previously returned `False` for a timestamp outside tolerance (same as
  an ordinary signature mismatch); it now raises `StripeWebhookError`,
  since a stale-but-otherwise-valid signature is a possible replay, a
  more specific finding than "didn't match." **Breaking API change** from
  the 2026-09-18 version of this function: the parameter is also renamed
  `tolerance_seconds` → `tolerance_sec` to match the merged-in code.
  Nothing else in this repo passed that kwarg by name except this
  module's own tests, which were updated.
- **Out-of-order webhook precedence (F-09) — the part that needed the
  most care.** `stripe_webhooks.py` gained `STATUS_RANK`/`can_transition()`/
  an `update_invoice_status()` that refuses to downgrade a status, but
  **the live webhook path never calls that function** —
  `stripe_webhook_server.py` calls `webhook_store.update_sales_log_status()`,
  which calls `AppsScript_Code.gs`'s `handleUpdateSalesLogStatus_` directly.
  Adding the precedence check only to the Python helper would have left
  production completely unprotected while the regression test passed —
  so the same `STATUS_RANK` table was **also** added to
  `AppsScript_Code.gs` (mirrored, not shared — a `.gs` file can't import
  Python) inside the same locked read-mutate-write execution that already
  exists there. `handleUpdateSalesLogStatus_` now returns
  `{found, applied}` instead of just `{found}`; `webhook_store.update_sales_log_status()`'s
  `payload` shape changed from a bare bool to `{"found": bool, "applied": bool}`
  accordingly — `stripe_webhook_server.py`'s `_apply_update()` was updated
  to read the new shape (the old `elif not result.payload:` check would
  have silently stopped firing, since a non-empty dict is always truthy
  regardless of its contents — caught by re-running the test suite, not
  by inspection).
- Reminder for whoever deploys this: **`AppsScript_Code.gs` changes only
  take effect once the Apps Script Web App is manually redeployed** (paste
  the file into Extensions → Apps Script → Deploy → new deployment) — this
  repo file is a copy of the source, not the running code.

### 4. Category-mismatch self-validation (F-04)
`listing_normalizer.normalize_listing()` used to derive `expected_keywords`
from the listing's own category/title/description when the caller didn't
supply any — making `opportunity_radar.detect_category_mismatch()`
self-cancelling (it validated the category against evidence manufactured
from that same category). Now defaults to an empty tuple; only an
independently-supplied taxonomy populates it.

This alone would have **silently disabled** category-mismatch detection
for every real source (nothing in this codebase currently supplies an
independent taxonomy), since the fallback branch in
`detect_category_mismatch()` needs *some* evidence to compare against.
Closed the gap with a second, still-independent check: `opportunity_radar.py`'s
own fixed `_CATEGORY_TERMS` map (never derived from the listing) is now
also checked in reverse — if the listing text strongly matches a
*different* recognized category (≥2 distinct terms, to avoid flagging on
one incidental word) and the claimed category shares no vocabulary with
that category, it's flagged as likely miscategorized. A camera listed
under "Clothing" now fires; a chair mentioned once under "Home & Garden"
does not (single-term hits don't meet the threshold — false-positive
guard per the session's explicit "do not raise the clean-listing
false-positive rate" requirement).

### 5. SKU collision (F-08)
`listing_bridge.build_master_listing()` used to fall back to the literal
string `"CRTC-ITEM"` when a flip had neither `sku` nor `source_listing_id`
— every such flip collapsed onto one SKU, silently overwriting each other
in `listing_store.upsert_listing()`'s `(sku, marketplace)` keying. New
`_stable_sku()` fallback hashes the flip's content **plus a fresh random
component** per call — deliberately not a pure content hash: two
independently-created flips can have identical `item_name`/`cost_basis`/
`notes` (two otherwise-identical $5 rings, entered by hand, at the same
moment), and a pure hash would still collide on those. The tradeoff:
calling `build_master_listing()` twice for the literal same flip dict now
produces two different fallback SKUs (two rows, not one updated in
place) — a duplicate a human can merge, which is a smaller problem than
two unrelated items silently sharing one identity.

### Tests
```
python3 -m pytest tests/test_p0_regression.py -q                 -> 19 passed
python3 -m pytest tests/test_stripe_webhooks.py tests/test_stripe_webhook_server.py tests/test_webhook_store.py -q -> 88 passed
python3 -m pytest tests/test_deal_workspace.py tests/test_auction_radar.py tests/test_auction_decision_flow.py tests/test_crtc_opportunity.py -q -> 25 passed
python3 -m pytest tests/ -q                                       -> 360 passed, 0 failed
python3 -m compileall -q .                                        -> exit 0
git diff --check                                                  -> exit 0 (no whitespace/conflict markers)
python3 -m pip check                                              -> No broken requirements found
```
Every number above is from an actual run in this session, not estimated.

### Known limitations / not done this pass
- `financial_intelligence.py` / `payments_adapter.py` / `crtc_learning.py` /
  `ebay_image_scan.py` remain unwired (unchanged from the 2026-09-20 file
  inventory entry above) — none of these are part of the decision-engine
  surface, out of scope here.
- The event-id idempotency parameters (`event_id`/`seen_event_ids`) added
  to `stripe_webhooks.update_invoice_status()` are exercised by tests but
  **not yet called from `stripe_webhook_server.py`** — the live path
  still relies on `AppsScript_Code.gs`'s status-precedence check alone
  for safety, not on event-id deduplication. Adding that would need a
  persisted "seen event ids" set in the Apps Script sheet (new schema),
  which is a real design decision, not a small patch — flagged, not done.
- Multi-tenant data isolation, live Stripe Connect end-to-end, ToS/privacy
  policy, and the dedicated security-audit pass (P0 items 14 onward in
  the master direction doc) are not started.
- Opportunity Radar's fuzzy/arbitrary typo detection (as opposed to its
  dictionary-based `_COMMON_TYPOS` list) is still basic — not addressed
  this pass.
- `AppsScript_Code.gs`'s `STATUS_RANK` table is a hand-mirrored copy of
  `stripe_webhooks.py`'s — the two must be kept in sync manually if either
  changes (a `.gs` file has no way to import from the Python module).

## 2026-09-20 — fix: wire pos.py/billing.py into the live Charge Customer tab
Follow-up to the same day's file-inventory pass below, which had flagged
(not yet fixed) that `app.py`'s "Charge Customer" tab created Stripe
charges via a raw inline Payment Link call instead of using `pos.py`.
Investigating further found the real bug was worse than a "wrong Stripe
primitive" style nit:

- The old flow never set `payment_intent_data[metadata][invoice_id]` on
  the created object, so a `charge.succeeded` webhook for it would have
  no `invoice_id` in its metadata for `stripe_webhooks.handle_charge_succeeded()`
  to read.
- It only appended to `st.session_state.charge_log_by_ws` — pure
  in-memory session state, never written to the persistent `sales_log`
  table `stripe_webhook_server.py`/`webhook_store.py` reconcile against.
  Refreshing the page or opening the app on another device lost the
  entire "Recent Charges" list.
- Net effect: the whole Stripe webhook reconciliation feature (hardened
  for replay-protection in the 2026-09-18 pass) was completely
  disconnected from the live POS UI — it had nothing to reconcile
  against, ever, regardless of webhook correctness.

Fix: `app.py`'s Charge Customer tab now calls `pos.create_pos_checkout()`
(the module that was already correctly built, already handling a dynamic
per-sale amount via a Checkout Session, already tagging `invoice_id` in
metadata) and persists the result as a `sales_log` row via
`storage.save_table(..., "sales_log", shared=True)`, using the exact
`"Invoice #"` / `"Status"` field names `AppsScript_Code.gs`'s
`handleUpdateSalesLogStatus_` and `stripe_webhooks.update_invoice_status()`
already expect (verified by reading `AppsScript_Code.gs` directly, not
assumed). "Recent Charges" now reads from the persisted table instead of
session state, and a manual "Check Payment Status" button
(`pos.check_payment_status()`) was added for the rows still "Awaiting
Payment" — this closes the gap between what `pos.py`'s own docstring
promised ("the POS tab's Check Status button already covers manual
reconciliation") and what the tab actually had, which was no such
button at all.

`pos.py` and `billing.py` are no longer marked "NOT CURRENTLY USED" —
their docstring headers were updated to say what wires into what.
`mail.py`/`mail_parse.py`/`drive_scan.py`/`crtc.py` remain unused; not
touched by this fix.

Tests: both modules had **zero** test coverage before this fix, despite
`pos.py` now being live payment-creation code — added `tests/test_pos.py`
(9 tests: rejects non-positive amount, missing secret key fails
gracefully, successful session creation sends the right cents/metadata,
two sales never collide on the same `invoice_id`, HTTP error / connection
failure both degrade to a failed result instead of crashing, and
`check_payment_status()`'s paid/unpaid/error paths) and
`tests/test_billing.py` (5 tests covering `verify_checkout_session()`'s
paid/unpaid/missing-customer-details/HTTP-error/connection-error paths).

```
python3 -m pytest tests/test_pos.py tests/test_billing.py -q  -> 15 passed
python3 -m pytest tests/ -q                                    -> 315 passed, 0 failed
                                                                    (300 baseline + 15 new)
python3 -m py_compile app.py                                   -> exit 0
```

Also removed a dead `import urllib.parse` from `app.py` left over from
the old inline Payment Link code (nothing else in `app.py` used it —
verified by grep before removing).

**Not done / explicitly out of scope for this fix:** `billing.py`'s
subscriber-paywall flow (`payment_link_url()`) is still not wired into
any paywall/subscription gate in `app.py` — that's a separate, unrelated
feature gap from the POS bug just fixed, and nothing asked for it this
pass.

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
  production app. **Fixed the same day, right after this entry was
  written — see the 2026-09-20 "fix: wire pos.py/billing.py" entry
  above.** The side-finding here turned out to be worse than a wrong-
  Stripe-primitive nit: the live flow never set an `invoice_id` or wrote
  a `sales_log` row, so webhook reconciliation had nothing to match
  against at all. `pos.py`/`billing.py` are both live code now, not dead.
- `billing.py` — at the time this entry was written, only consumer was
  `pos.py` (also dead then). Both are wired in now — see above.
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


## 2026-09-20 — Windows Store deployment pass

Added a Windows Store deployment plan on branch `feat/crtc-windows-store`. The planned architecture is a thin Windows App SDK/WinUI 3 + WebView2 shell around the existing HTTPS Streamlit application, preserving current web behavior. Added Windows Store README, launch plan, build checklist, and ignore rules. No native rewrite or billing implementation was added. MSIX/build testing is NOT claimed because this environment is not Windows; validation must run on the Windows development machine/CI before merge.


## 2026-09-20 — iOS App Store deployment pass

Added an iOS App Store deployment plan on branch `feat/crtc-ios-store` using a thin native WKWebView shell around the production HTTPS Streamlit application. Production URL configured in the iOS documentation: `https://appraze-ai-dkc8kpa7pbtzhgwpgztqyh.streamlit.app/`. No Streamlit behavior changes, native rewrite, or billing implementation was added. Actual Xcode/archive/TestFlight/App Store validation is NOT claimed because this environment is not macOS/Xcode. The next execution point is to create/build the iOS shell on a Mac, run a physical iPhone smoke test, archive, and upload to TestFlight before App Review.
