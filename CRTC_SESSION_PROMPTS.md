# CRTC Finish Prompt Pack (VS Code / Claude Code)

**Workspace:** Unzip `CRTC-P0-hardened.zip` and open that folder only.  
**Order:** Session 0 → 9. One session per chat. Do not skip ahead if tests fail.  
**Models:** Sonnet 5 default · Opus 5 only if stuck on architecture/security.

Add this line to every API session to save money:
```
Prefer minimal diffs. Do not re-read the entire repo. Only open files named in this prompt. Stop when tests for this session are green.
```

---

## Session 0 — Bootstrap (always first)

```
You are working in the CRTC repo that already has P0 fixes applied (decision_policy.py, hardened stripe_webhooks.py, number_normalize.py, test_p0_regression.py, updated CRTC_HANDOFF.md).

Rules for every session:
1. Do NOT add major new features.
2. Do NOT rewrite systems that already pass tests (money math, flip lifecycle, comps median, P0 regressions).
3. FIX → TEST → REPORT. Never say "tests pass" without running them.
4. After changes: run `python -m pytest tests/test_p0_regression.py -q` and any related tests. Paste the real output.
5. Update CRTC_HANDOFF.md only if behavior or public API changed.
6. One logical commit-sized change per session. Small diffs.

First: confirm these files exist and briefly state what each does:
- decision_policy.py
- stripe_webhooks.py
- number_normalize.py
- tests/test_p0_regression.py
- CRTC_HANDOFF.md

Then list remaining open gaps from CRTC_HANDOFF.md. Do not implement yet.
```

---

## Session 1 — Wire decision_policy everywhere

```
Goal: Every BUY/PASS/REVIEW path must go through decision_policy.evaluate_deal or build_deal_workspace_record. No module may invent its own 70% or ROI threshold.

1. Search the repo for independent BUY logic (70%, max_bid, AT CEILING, buyer_premium, shipping unknown treated as 0).
2. Update these call sites to use decision_policy (do not leave parallel formulas):
   - deal_workspace.py (should already be thin)
   - auction_radar.py
   - crtc_opportunity.py
   - any pages under pages/ that decide BUY
3. Preserve UI keys the Streamlit pages expect (decision, max_bid, all_in, reason, confidence).
4. Unknown shipping/premium must still return REVIEW or CONDITIONAL BUY — never hard BUY with missing cost as $0.
5. Run:
   python -m pytest tests/test_p0_regression.py tests/test_deal_workspace.py tests/test_auction_radar.py tests/test_crtc_opportunity.py -q --tb=line
6. Report: files changed, test output, any call sites you could not safely migrate (and why).
```

---

## Session 2 — Buyer premium + number_normalize consistency

```
Goal: buyer_premium is percentage points everywhere. Dollars use buyer_premium_amount. Fractions 0–1 mean percent (0.18 → 18).

1. Audit every read/write of buyer_premium / buyer_premium_pct / premium across:
   acquisition_hunter.py, auction_costs.py, listing_normalizer.py, comps paths, pages
2. Route parsing through number_normalize.parse_percent_points and parse_money.
3. Rename ambiguous fields only where safe; keep backward-compatible aliases if needed.
4. Add tests to tests/test_p0_regression.py (or a new test_number_normalize.py) for:
   "18", "18%", 0.18, "0.18", "$18", invalid, negative
5. Run related tests + test_p0_regression.py. Paste output.
6. Short note in CRTC_HANDOFF.md under "buyer_premium convention".
```

---

## Session 3 — Stripe webhook server + Apps Script alignment

```
Goal: stripe_webhook_server.py and any Apps Script status handling match the hardened stripe_webhooks.py rules.

Rules already in stripe_webhooks.py:
- 300s timestamp tolerance (replay reject)
- any valid v1 signature accepted
- amount_refunded for money (not boolean refunded)
- status rank: Refunded > Partially Refunded > Paid > Failed
- non-ASCII / malformed → StripeWebhookError, not 500

1. Read stripe_webhook_server.py and AppsScript_Code.gs status update paths.
2. Align them with the above (ordering, refund field, no silent overwrite).
3. Ensure process_webhook_event results are applied via update_invoice_status with event_id idempotency if a store exists.
4. Extend tests/test_stripe_webhooks.py / test_stripe_webhook_server.py for:
   - stale timestamp rejected
   - full + partial refund amounts
   - Paid after Refunded ignored
   - duplicate event_id no-op
5. Run those tests + test_p0_regression.py. Paste output.
```

---

## Session 4 — Category mismatch through real pipeline

```
Goal: Misclassified category is detectable on the REAL path: normalize_listing → analyze / opportunity_radar (not only a direct low-level call).

1. Confirm listing_normalizer does NOT set expected_keywords from the listing's own category (P0 should have this).
2. Trace opportunity_radar / holy grail path: where category mismatch is computed.
3. Ensure wrong category + independent taxonomy (or empty expected_keywords + title/desc conflict) can fire REVIEW/flag on the production pipeline.
4. Add a regression test that goes through normalize_listing → radar/analyze with a deliberately wrong category (e.g. camera listed as Clothing) and asserts a mismatch signal.
5. Do NOT raise clean-listing false positive rate. Add at least one clean listing that must stay unflagged.
6. Run tests/test_opportunity_radar.py tests/test_listing_normalizer.py tests/test_p0_regression.py -q --tb=line
```

---

## Session 5 — SKU / listing identity + concurrent safety

```
Goal: No two inventory items share a SKU. Never use the constant "CRTC-ITEM".

1. Confirm listing_bridge uses stable unique SKU generation (P0).
2. Check listing_store.py / inventory_bridge.py / flip_ledger for any other fallback ID that could collide.
3. Add tests:
   - 50 manual flips without source_listing_id → 50 distinct SKUs
   - repeated import of same source id stays stable
   - concurrent-style sequential creates do not overwrite
4. Run tests/test_listing_bridge.py tests/test_listing_store.py tests/test_p0_regression.py
5. Report any remaining single-shared-workspace tenancy risk (document only; do not implement full multi-tenant DB unless already partially present).
```

---

## Session 6 — Invalid financial inputs at every boundary

```
Goal: NaN, Inf, negative prices, boolean-as-number, overflow strings never produce BUY or STRONG BUY.

1. Audit finance.calc_deal, decision_policy.evaluate_deal, listing_normalizer price paths, auction_costs.
2. Ensure system-boundary validation (normalize + evaluate) rejects or REVIEW.
3. Extend test_p0_regression.py parametrize cases if gaps remain.
4. Run full:
   python -m pytest tests/test_p0_regression.py tests/test_finance.py tests/test_listing_normalizer.py -q --tb=line
5. Paste full summary line (N passed / N failed).
```

---

## Session 7 — Security pass (listing text = untrusted)

```
Goal: Marketplace listing title/description cannot become instructions. No secrets in repo. Auth boundaries noted.

1. Search for places listing text is passed into prompts, eval, shell, SQL, or HTML without escaping.
2. Document findings in a short SECURITY_NOTES.md (or section in CRTC_HANDOFF.md):
   - injection risks found
   - what was fixed vs deferred
   - auth/session files that still need human review
3. Fix only clear, small, safe issues (escaping, refuse to exec listing text). Do not redesign auth in this session.
4. Confirm .gitignore covers .env, secrets, key files.
5. Run existing auth tests if present: tests/test_auth.py -q
6. Do not invent a full OAuth redesign.
```

---

## Session 8 — HANDOFF + launch checklist freeze

```
Goal: Single source of truth for the next human/agent.

Update CRTC_HANDOFF.md to include:
1. What P0/P1 is DONE (with file names)
2. What remains blocked for public beta (tenancy, live Stripe Connect E2E, ToS/privacy, full security audit)
3. Exact test commands to run before every release
4. Canonical decision policy summary (70% acquisition + ROI tiers + unknown costs ≠ 0)
5. buyer_premium unit convention
6. Webhook status precedence
7. "Do not add features until: [checklist]"

Also create or update a short LAUNCH_BLOCKERS.md with only the hard gates (checkbox list).

Do not implement new features. Docs only + verify tests still green:
python -m pytest tests/test_p0_regression.py -q
```

---

## Session 9 — Final gate (run once before any beta invite)

```
Final production gate. Do not write product features.

1. Run:
   python -m pytest tests/test_p0_regression.py tests/test_stripe_webhooks.py tests/test_finance.py tests/test_deal_workspace.py tests/test_listing_bridge.py tests/test_auction_costs.py -q --tb=line
2. Paste the full last summary line.
3. Confirm these statements are TRUE in code (cite file+symbol):
   - One canonical decision engine
   - Unknown material costs cannot become hard BUY
   - Webhook replay rejected by timestamp
   - Refunds use amount_refunded
   - Out-of-order cannot downgrade Refunded → Paid
   - Category expected_keywords not derived from own category
   - SKUs unique without "CRTC-ITEM"
4. List anything still false or untested (especially live Stripe Connect and multi-tenant isolation).
5. Output a 10-line "safe to invite friendly beta?" verdict: YES only if all High/Medium code findings are closed; otherwise NO + top 3 blockers.
```

---

## After each session

1. Commit with a clear message (e.g. `fix: wire decision_policy into auction_radar`).
2. Append one line to SESSION_LOG.md: date, session #, tests result, files touched.
3. If tests failed → repeat the same session with the failure log at the top. Do not start the next number.