# Appraze Audit Fixes — Completion Report

Repo: `~/workspace/crtc-work-fixes` (git-initialized, local identity only, never pushed to GitHub, per instructions).

All 9 requested fixes are **done**. Full test suite: **401 passed**, 3 pre-existing failures in `tests/test_ebay_sell.py` (unrelated to any of the 9 fixes — `ebay_sell.py` and its test file were never touched by this work; confirmed these failures exist in the baseline commit, not introduced by these changes).

Run tests with: `/tmp/crtcvenv2/bin/python -m pytest -q` (a venv with pytest/fastapi/bcrypt/requests/httpx/streamlit installed — the repo's own environment may differ).

---

## Fix #1 — Stripe idempotency key — DONE

`pos.py`'s `create_pos_checkout()` sends header `Idempotency-Key: pos-checkout-{invoice_id}` on every Checkout Session creation POST (`pos.py:111`), keyed off a freshly generated `invoice_id` so a retried request for the same sale can't double-charge. This app calls Stripe's raw HTTP API via `requests` (no `stripe` SDK), so the key is a manual header rather than an SDK kwarg.

This was implemented in a prior run and folded into the baseline commit. This session found it was untested and added `tests/test_pos.py::test_sends_idempotency_key_derived_from_invoice_id`, which passes.

**Verified**: read the code, confirmed the header is genuinely sent and correctly scoped per-sale, added and ran the missing test.

## Fix #2 — Webhook reconciliation failures return 5xx — DONE

`stripe_webhook_server.py`: `_apply_update()` returns `False` only when persisting the reconciled sale actually fails; the endpoint then returns `JSONResponse(status_code=502, ...)`, distinct from legitimate no-op outcomes (e.g. row not found yet, downgrade rejected) which still return 200 so Stripe doesn't retry those forever.

**Verified**: read the code; `tests/test_stripe_webhook_server.py` asserts `resp.status_code >= 500` on a forced failure. Passes.

## Fix #3 — bcrypt/argon2 password hashing + brute-force protection — DONE

`auth.py`: admin credentials verified via `bcrypt.checkpw` with a regex guard confirming the stored value is actually a bcrypt hash. Login lockout: `MAX_LOGIN_ATTEMPTS = 5` with exponential backoff up to 15 minutes, tracked process-globally under a thread lock, wired into `_admin_login`.

**Note** (not part of this fix's scope, flagged for awareness): the separate tester-signup path still SHA-256-hashes client-side — this is a different backend (Google Apps Script), documented as such in the module docstring, not the admin login path this fix targets.

**Verified**: read the code; `tests/test_auth.py` covers both the bcrypt path and the lockout/backoff behavior thoroughly. Passes.

## Fix #4 — Buyer-premium percentage parsing — DONE

`number_normalize.py`'s `parse_percent_points()` correctly handles `"18%"` → 18.0, `"18"` → 18.0, `0.18` → 18.0 (fraction heuristic for values strictly between 0 and 1), and `"18.5%"` → 18.5. Wired into `auction_costs.py`.

**Verified**: read the code; `tests/test_p0_regression.py::test_f06_buyer_premium_fraction_normalized` explicitly checks all four format variants. Passes.

## Fix #5 — Non-auction BUY verdict must use all-in cost — DONE

Root cause was two bugs in `decision_policy.py`'s non-auction (`require_shipping=False`) cost path:
- A known shipping dollar amount was discarded and hardcoded to `0.0` regardless of the actual value supplied.
- `max_bid_or_price` for non-auction listings never subtracted known fixed costs (shipping/fees) before comparing against the target price, unlike the auction branch.

Fixed both. Added a `tax` field to `listing_normalizer.py`'s `NormalizedListing` and wired shipping/fees/tax through in `crtc_opportunity.py`'s non-auction path (previously it called `evaluate_deal()` with none of these at all).

**Tests**: added `tests/test_crtc_opportunity.py::test_opportunity_all_in_cost_includes_shipping_and_tax_not_just_price` and `test_opportunity_still_buys_when_all_in_cost_clears_target`. All 5 tests in that file pass. Also verified via direct interactive calls to `evaluate_deal()`.

## Fix #6 — Dashboard verdict must agree with pipeline verdict — DONE

Root cause: `app.py`'s `recalc()` used naive `finance.deal_roi()` (no platform-fee adjustment) for the Dashboard, while the Profit Calculator and acquisition pipeline both use fee/premium-adjusted `finance.calc_deal()` — same numbers could show BUY on one and something less rosy on the other.

Added `finance.dashboard_deal_result()` — a `calc_deal()` wrapper with `premium_pct` pinned to 0 (Dashboard's "Cost" column is already the amount actually paid, premium included, so applying a premium again would double-count it) — and switched `recalc()` to use it. Also removed a redundant, now-unnecessary separate verdict recomputation in the "quick profit view" section that could have drifted from the Dashboard's own verdict.

**Tests**: added 4 tests in `tests/test_finance.py::TestDashboardDealResult`. All 43 tests in that file pass.

## Fix #7 — CSV re-import must deduplicate — DONE

Root cause: the CSV import block never checked for duplicate rows before concatenating. Compounded by Streamlit's rerun model — the uploaded file persists across reruns triggered by *any* unrelated widget interaction elsewhere in the app, so without dedup, rows could silently multiply even without the user deliberately re-uploading.

Fixed with content-based row deduplication: rows are compared (as strings, so type/formatting differences like `""` vs `NaN` don't defeat an otherwise-identical match) against both the existing table and within the imported file itself, both before the initial concat.

**Tested**: no pytest harness covers `app.py`'s Streamlit UI code (`tests/test_smoke.py` only import-checks pure sub-modules, never imports `app`). Verified with a standalone manual script exercising the dedup logic directly — first import adds rows, re-running the same import finds 0 new rows.

## Fix #8 — Filtered deletions must persist — DONE

Root cause: the Dashboard's filtered `st.data_editor` pushed edits back via `st.session_state.deals.update(edited)` (pandas `.update()` never removes rows) plus a positional `len(edited) > len(filtered)` check for detecting additions — so deleting a row in a filtered view never removed it from the master table, and the addition check couldn't detect deletions at all.

Investigated Streamlit's `data_editor` internals directly (read `elements/widgets/data_editor.py` in the installed package) and confirmed: surviving/edited rows keep their original index label; only genuinely new rows get freshly minted labels. Fixed by diffing `filtered.index` against `edited.index` to find deleted and added labels explicitly, and restricting `.update()` to the kept/edited intersection (a newly added row's synthetic label is minted from the filtered view's own small index range and can otherwise collide with an unrelated master-table row that was simply filtered out of view, silently corrupting it).

Also fixed a self-introduced regression: fix #6's new "Verdict" column wasn't being dropped from the filtered `data_editor`/equality-check calls, which would have exposed it as editable and pushed it incorrectly into the master table.

**Tested**: no pytest harness for `app.py`'s UI code. Verified by extracting the exact index-diffing logic into a standalone script and exercising delete+edit+add (including an engineered index-collision scenario), pure deletion, pure addition, and pure cell-edit — all four behaved correctly.

## Fix #9 — Analyzer model ID + image size limit — DONE

Model ID confirmed correct in an earlier session: `app.py`'s Analyzer tab sends `"model": "claude-sonnet-5"`, which is the correct current model ID. No change needed.

Added an 8 MB image size gate before sending to the API: a fast-path check against the uploaded file's `.size` attribute (avoids reading a huge file into memory at all), plus a fallback check against the actual byte length after `read()` in case `.size` is ever unavailable. Either rejection shows the user the file's actual size and skips the API call entirely — no base64 encoding, no request built.

**Tested**: no pytest harness for `app.py`'s UI code. Verified by extracting the gating logic into a standalone script against a fake uploaded-file object: small image sent, no-photo/text-only sent, 9 MB rejected pre-read, exactly 8 MB allowed (boundary is strictly `>`), 8 MB + 1 byte rejected, empty-input warning path all correct.

---

## Honesty notes — what was NOT independently verified end-to-end

- Nothing in this repo has browser/UI-level testing for `app.py`'s Streamlit code (fixes #6, #7, #8, #9's UI-facing parts). All were verified either through `finance.py`/`decision_policy.py`/`crtc_opportunity.py` unit tests (pure logic, fully testable) or through standalone non-pytest scripts that exercise the exact extracted logic — not through an actual running Streamlit app in a browser. This is a testing limitation of the repo, not something skipped in this session.
- Fix #1's idempotency key is verified for the POS Stripe Checkout flow (`pos.py`) specifically; `billing.py`'s subscriber Payment Link flow doesn't create Checkout Sessions itself and wasn't in scope.
- Fix #3's brute-force lockout is process-global, in-memory state (not persisted/shared across multiple app instances) — fine for this app's single-shared-admin-login model, but worth knowing if the app is ever run as multiple replicas behind a load balancer.
- The 3 `test_ebay_sell.py` failures are pre-existing (present in the baseline commit, in a module never touched by any of these 9 fixes) and were left as-is — not in scope.

## Commits (all local, never pushed)

```
8867062 Add missing test coverage for POS Stripe idempotency key (fix #1)
d5a2756 Fix #9: reject AI Analyzer images over 8 MB before sending
e49e534 Fix #8: filtered-view row deletions now persist to the master table
f7873e8 Fix #7: CSV re-import no longer creates duplicate deal rows
bab3646 Fix #6: unify Dashboard verdict with the fee-adjusted pipeline math
c5d70a6 Fix #5: non-auction BUY verdict now uses true all-in cost
9381e2e Baseline: Appraze repo as found, including prior run's partial audit fixes
```
