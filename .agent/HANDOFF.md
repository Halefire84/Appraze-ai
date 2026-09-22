# CRTC / Appraze — Agent Handoff

Last updated: 2026-09-22 (follow-up session, on `main` directly — the
2026-09-21 session's branch was squash-merged as PR #25 and auto-deleted).

This file is the authoritative, self-contained state summary for the next
agent. `CRTC_HANDOFF.md` is a longer append-only session log kept for
history; this file is the current-state snapshot. If the two disagree,
trust this file and re-verify by running the test commands below.

## 2026-09-22 follow-up: buyer_premium naming collision, crtc.py removed

Asked to cross-check everything ChatGPT's parallel session
(`CHATGPT_HANDOFF.md`, `CRTC_SESSION_PROMPTS.md` — Sessions 0-9) had
flagged, against actual current source, and to cut anything not worth
keeping.

**Real bug found and fixed:** `acquisition_hunter.py`'s liquidation-lot
pipeline (`estimate_max_bid`/`score_acquisition`, used by
`pages/2_📦_Liquidation_Surplus.py` and `pages/3_🏛️_Government_Electronics.py`
via `crtc_hunt_engine.py`) summed a bare `listing.get("buyer_premium")` as
a **dollar amount**. `decision_policy.py`'s unrelated auction pipeline
(`pages/3_💰_Deal_Workspace.py`, `auction_radar.py`) reads that exact same
key name as **percentage points** (documented there as a "legacy key").
Two different unit conventions sharing one ambiguous field name — the
exact class of bug the audit's "buyer_premium must have ONE documented
unit convention" item warns about. If a listing dict were ever passed to
the wrong pipeline, the value would have been silently misinterpreted.
Fixed by renaming the dollar-amount side to the explicit
`buyer_premium_amount` in `acquisition_hunter.py` and its two page
callers (the percentage-points side, `decision_policy.py`'s legacy input
alias, was intentional and left untouched — it already has an explicit
`buyer_premium_pct` preferred key, this was a deliberate backward-compat
read, not a bug). Added
`tests/test_p0_regression.py::test_acquisition_hunter_reads_explicit_amount_key`
and `::test_acquisition_hunter_ignores_legacy_ambiguous_key` to lock this
in — the second test specifically proves the old ambiguous key is no
longer read as a dollar amount.

**Dead code removed:** `crtc.py` (178 lines) — confirmed via grep that
nothing imports it anywhere in source, docs, or tests beyond passing
mentions; its own docstring already said "NOT CURRENTLY USED... superseded
by `pages/5_Cross_List.py`... safe to delete once someone confirms
`pages/5_Cross_List.py` fully covers its functionality" — confirmed
(`pages/5_Cross_List.py` reads `sku` from `listing_bridge.build_master_listing()`
correctly, not a hardcoded fallback). Updated the 3 files that referenced
it in passing (`AI_NOTES.md`, `tests/test_listing_store.py` comment, this
file).

**Explicitly NOT cut, despite being unwired/unimported** (checked each
against `AI_NOTES.md`'s existing "Built but NOT wired" inventory and the
docs it points to, rather than assuming "unused = cruft"):
- `financial_intelligence.py`, `payments_adapter.py` — deliberate,
  documented roadmap scaffolding for `CRTC_FINANCIAL_ROADMAP.md`'s
  Plaid/bank-connection plan; `payments_adapter.py` specifically is what
  OPEN PRODUCT REQUIREMENTS item 1 (pluggable payment processor) builds
  on next.
- `crtc_learning.py` — tested, tied to `docs/CRTC_CONTINUOUS_HUNT.md`'s
  design.
- `ebay_image_scan.py` — tested, "recent, deliberate, not legacy" per
  `AI_NOTES.md`.

A prior session already made this same call and left a note: this
environment treats file deletion as needing explicit confirmation, and
none of those four "not wired" but roadmap-anchored files should be
deleted without the owner weighing in specifically on the roadmap, not
just on unwired-ness.

**Tests:** `python3 -m pytest -q` → 373 passed, 0 failed (371 prior + 2
new). `python3 -m compileall -q .` → exit 0. Run in this session, on
`main` directly.

## What the 2026-09-21 session did (superseded branch, content is on `main`)

1. **Fixed 5 collapsed-line syntax errors in `app.py`** (lines ~170, 368,
   762, 765, 768, 968 — the task named 5, one adjacent collapse at 762 was
   caught in the same block). Multiple statements/comments had been
   concatenated onto single lines with no newline, e.g.
   `s = search.lower()        filtered = filtered[...]`. Fixed by
   restoring line breaks. Verified with `python3 -c "import ast;
   ast.parse(open('app.py').read())"` and `python3 -m compileall -q .`.

2. **Closed a real admin-trust vulnerability in `AppsScript_Code.gs`.**
   `resolveOwnerKey_()` (used by `save_data`/`load_data`, i.e. the shared
   admin workspace), `handleReserveAiUsage_()`, and `handleGetAiUsage_()`
   all derived admin status from the client-supplied `params.is_admin`
   request parameter. Any caller of the Apps Script endpoint could send
   `is_admin=true` and (a) read/write the shared `admin_shared` storage
   row regardless of actual account, and — worse — (b) with a **username
   that doesn't even exist as an account**, pass the "is this a real user"
   check and reserve AI usage at the admin quota (500/month, 25/day)
   instead of being rejected. Fixed: admin status is now looked up from
   the `Users` sheet by username only (`findUser_(usersSheet,
   username).isAdmin`); `params.is_admin` is never consulted for any
   authorization decision. `resolveOwnerKey_`, `handleSaveData_`, and
   `handleLoadData_` now take `usersSheet` as a parameter.
   **Important:** `CRTC_GAP_CLOSURE_REPORT.md` (dated 2026-09-19) claims
   this exact fix was already made, but that report describes work done
   in an external zip (`CRTC-gap-closure-2026-09-19.zip`) that the report
   itself says was never pushed to the source tree. The bug was live in
   this repo's `AppsScript_Code.gs` until this session. Treat claims in
   that report about what's "closed" with skepticism unless verified
   against actual source, same as this file should be.
   Verified with `node --check` (syntax only — Apps Script has no unit
   test harness reachable from this environment; there is no live Google
   Sheets deployment to exercise `findUser_`/sheet I/O against). This is
   a known verification gap, not a claim of full test coverage for the
   `.gs` file.

3. **The "8 P0 audit fixes"** — the task referenced
   `crtc-audit/claude-code-implementation-brief-2026-09-20.md`. **That
   file does not exist anywhere in this repository** (checked this
   branch, `main`, and full git history — confirmed via
   `git ls-tree -r --name-only` on both branches and `git log --all
   --diff-filter=A --name-only`). It was never committed.
   `CRTC_HANDOFF.md`'s "Unresolved issues carried into the next session"
   section (dated 2026-09-20) lists what appears to be the same 8 items
   from the "CRTC — New Master Development Direction" doc. Cross-checked
   each against current source and the existing regression suite
   (`tests/test_p0_regression.py`, findings F-01…F-13):

   | # | Item | Status | Evidence |
   |---|------|--------|----------|
   | 1 | Canonical BUY decision engine (unify 70%-rule / 40% ROI) | **Done** | `decision_policy.py` — single `evaluate_deal()`; `auction_radar.py`, `crtc_opportunity.py`, `deal_workspace.py` all delegate to it, no duplicate math | `test_f01_*` |
   | 2 | Stripe webhook replay protection (timestamp tolerance, signature rotation, durable event-idempotency) | **Done** (event-idempotency wired *this session*) | `stripe_webhooks.verify_stripe_signature` (5 min tolerance, any valid `v1=`); event-id dedup now persisted per-row in `sales_log` (`_last_event_id`, `AppsScript_Code.gs::handleUpdateSalesLogStatus_`), wired through `webhook_store.update_sales_log_status(event_id=...)` and `stripe_webhook_server.py::_apply_update` | `test_f02_*`, `test_f13_*`, `tests/test_webhook_store.py::test_duplicate_event_id_reported` |
   | 3 | Stripe refund accounting (amount, not boolean) | **Done** | `stripe_webhooks.handle_charge_refunded` uses `amount_refunded` cents, never the `refunded` boolean; distinguishes PAID/PARTIALLY_REFUNDED/REFUNDED | `test_f03_*` |
   | 4 | Category-mismatch detection (independent taxonomy) | **Done** | `listing_normalizer.py` no longer self-derives `expected_keywords` from the listing's own category; `opportunity_radar.detect_category_mismatch()` requires an independently-supplied taxonomy | `test_f04_*` |
   | 5 | Financial input validation (NaN/Inf/negative never → BUY) | **Done** | `number_normalize.py` (`parse_money`/`parse_percent_points` reject NaN/Inf/negative/bool-as-number); `decision_policy.evaluate_deal` returns REVIEW for any invalid number | `test_f10_*`, `test_f11_*`, `test_parse_money_common_forms` |
   | 6 | Unknown acquisition costs never silently $0 | **Done** | `decision_policy.py` cost states `KNOWN\|UNKNOWN\|ESTIMATED\|NOT_APPLICABLE`; unknown required shipping/premium → REVIEW/CONDITIONAL_BUY with `costs_complete=False` and the assumption listed in `warnings` | `test_f05_*` |
   | 7 | Buyer-premium unit ambiguity | **Done** | `number_normalize.parse_percent_points` — single documented convention (fraction/percent-string/points all normalize to points); `buyer_premium_pct` naming used at call sites | `test_f06_*` |
   | 8 | SKU/listing-identity collisions (`CRTC-ITEM` fallback) | **Done** | `listing_bridge.build_master_listing()`/`_stable_sku()` generate collision-safe IDs, never `"CRTC-ITEM"`; the live Cross-List page (`pages/5_Cross_List.py`) consumes this. The one residual literal `"CRTC-ITEM"` fallback lived in dead code (`crtc.py`, superseded by `pages/5_Cross_List.py`), removed 2026-09-22 | `test_f08_*` |

   Also covered by the same suite but not in the original 8-item list:
   F-09 (out-of-order webhook can't downgrade a more-final status), F-12
   (non-ASCII signature → controlled rejection, never a raw exception).

   **Net: all 8 items are implemented and covered by passing regression
   tests.** The one genuine gap found and closed this session was #2's
   durable event-idempotency (previously implemented in
   `stripe_webhooks.update_invoice_status(event_id=, seen_event_ids=)`
   but never called from the live `stripe_webhook_server.py` path — see
   `CRTC_HANDOFF.md`'s "Known limitations" note dated 2026-09-20). It's
   now wired end-to-end; see the table above.

## Canonical modules (single source of truth — do not reimplement)

- **Decision engine:** `decision_policy.py::evaluate_deal()` /
  `build_decision()`. All BUY/PASS/REVIEW/CONDITIONAL_BUY decisions go
  through this. Constants: `ACQUISITION_TARGET_PCT=70.0`,
  `ROI_BUY_FLOOR_PCT=40.0`, `ROI_STRONG_BUY_PCT=60.0`,
  `ROI_AT_CEILING_PCT=20.0`, `ROI_BORDERLINE_PCT=5.0`. Cost states:
  `COST_KNOWN`/`COST_UNKNOWN`/`COST_ESTIMATED`/`COST_NOT_APPLICABLE`.
- **Financial parsing/normalization:** `number_normalize.py` —
  `parse_money()`, `parse_percent_points()`. Use these anywhere a
  marketplace/user-supplied numeric or currency/percent string needs
  parsing; never hand-roll another regex/float() call for this.
- **Stripe webhook verification & state:** `stripe_webhooks.py` —
  `verify_stripe_signature()` (timestamp tolerance + any valid `v1=`
  signature), `process_webhook_event()`, `handle_charge_refunded()`,
  `can_transition()`/`status_rank()` (STATUS_RANK precedence). Live HTTP
  path: `stripe_webhook_server.py`. Persistence: `webhook_store.py` →
  `AppsScript_Code.gs`.
- **Webhook state precedence (out-of-order delivery):** rank order
  `Awaiting Payment(0) < Failed/Payment Failed(1) < Paid/Paid (Card)(2) <
  Partially Refunded(3) < Refunded(4)`. Defined independently in
  `stripe_webhooks.py::STATUS_RANK` (Python, in-memory callers) and
  `AppsScript_Code.gs::SALES_LOG_STATUS_RANK_` (the actual live-path
  enforcement point — `stripe_webhook_server.py` calls
  `handleUpdateSalesLogStatus_` directly, not the Python precedence
  check). **These two tables must be hand-kept in sync** — a `.gs` file
  cannot import from a Python module. If you change one, change both.
- **Event idempotency:** `_last_event_id` persisted per invoice row
  inside the `sales_log` JSON payload (no new sheet/schema). Set by
  `AppsScript_Code.gs::handleUpdateSalesLogStatus_` when `event_id` is
  passed and differs from the stored value; a matching `event_id` is
  reported back as `duplicate: true` and skipped entirely.
- **Inventory/listing identity:** `listing_bridge.py::build_master_listing()`
  / `_stable_sku()`. Never fall back to a fixed literal SKU.
- **Admin status (Apps Script):** `findUser_(usersSheet, username).isAdmin`
  is the only authoritative source. Never trust a client-supplied
  `is_admin`/`params.is_admin` value for any authorization or quota
  decision — client input is a *request*, not a *fact*.

## Security assumptions

- Marketplace listing content (title/description/category) is untrusted
  input. `listing_normalizer.py`/`opportunity_radar.py` treat it as data,
  never as instructions; no AI/LLM path in this repo currently parses
  listing content as a prompt (the AI Analyzer tab in `app.py` sends
  user-supplied photo/description text as data to Anthropic's vision
  API, not as system instructions — worth re-verifying if that flow
  changes).
- The Apps Script endpoint is gated by a shared `TOKEN` (Streamlit
  secret `APPS_SCRIPT_TOKEN`), not per-user auth — anyone with the token
  can call any action. Authorization *within* an authenticated call
  (which owner_key to touch, whether admin quota applies) must never
  depend on request parameters the caller controls; it must be re-derived
  from the `Users` sheet every time. This is the exact class of bug fixed
  in this session — audit any new Apps Script action against this rule
  before merging.
- `ADMIN_SETUP_CODE`/`SHEET_ID`/`TOKEN` in `AppsScript_Code.gs` are
  placeholders in source control by design; real values live only in the
  deployed Apps Script project + Streamlit secrets. If this repo ever had
  real values committed, they must be treated as compromised and rotated
  (see the file's own header comment).

## Test commands (run before claiming anything passes)

```
pip install pytest -r requirements.txt -r requirements-webhook.txt
python3 -m compileall -q .                    # -> exit 0
python3 -m pytest -q                          # -> 371 passed, 0 failed
python3 -m pytest tests/test_p0_regression.py -q   # -> 21 passed
```

`AppsScript_Code.gs` has no Python-reachable test harness. Verification
for it in this session was limited to `node --check <copy-as-.js>` for
syntax validity plus manual review — there is no live Google Sheets
deployment in this environment to exercise `findUser_`/sheet I/O against.
Flag this explicitly rather than claiming it's covered by the pytest run.

## Actually run this session (2026-09-21)

```
$ python3 -m compileall -q .
(exit 0)

$ python3 -m pytest -q
371 passed, 11 warnings in 1.43s
```
11 warnings are pre-existing `DeprecationWarning`s from `starlette`/`httpx2`
dependencies, unrelated to this session's changes.

## Known limitations / not done (carried forward, still accurate)

- `financial_intelligence.py` / `payments_adapter.py` / `crtc_learning.py`
  / `ebay_image_scan.py` remain unwired into any live page — unchanged
  this session, out of scope for the P0 items.
- Multi-tenant data isolation hardening beyond the admin-auth fix above,
  live Stripe Connect end-to-end testing, ToS/privacy policy legal
  review, and the dedicated security-audit pass (P1/P2 items — auth,
  secrets, rate limiting, IDOR, dependency vulnerabilities, mobile/
  Windows/web deployment readiness) are not started this session.
- Opportunity Radar's fuzzy/arbitrary typo detection (beyond the
  dictionary-based `_COMMON_TYPOS` list) is still basic.
- `AppsScript_Code.gs`'s `SALES_LOG_STATUS_RANK_` is a hand-mirrored copy
  of `stripe_webhooks.py`'s `STATUS_RANK` — see "Webhook state
  precedence" above.
- The referenced audit brief file
  (`crtc-audit/claude-code-implementation-brief-2026-09-20.md`) does not
  exist in this repository. If the user has it, it should be added to the
  repo (e.g. under `crtc-audit/`) so future sessions can verify against
  it directly instead of reconstructing intent from `CRTC_HANDOFF.md`.

## Unresolved issues for the next session

Per the user's standing P1/P2 priority list (see conversation/prompt
history, not reproduced here in full): security audit (auth, secrets,
rate limiting, IDOR, injection, dependency vulns), AI/agent prompt-
injection boundary review once an LLM path reads listing content more
directly, and the Android/iOS/Windows/Web production-readiness review.
None of these are started this session — P0 items above were the
explicit priority and are now closed.
