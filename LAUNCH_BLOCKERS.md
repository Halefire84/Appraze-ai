# CRTC Launch Blockers

Hard gates only — not a general TODO list. See `CRTC_HANDOFF.md` for full
implementation detail and `CHATGPT_HANDOFF.md` / `CRTC_SESSION_PROMPTS.md`
for the hardening-session history behind these items.

Last verified: 2026-09-20 — `python3 -m pytest tests/ -q` -> 367 passed, 0 failed.

## Stage A — Code-hardened (owner-only use)

- [x] Canonical BUY/PASS/REVIEW decision engine (`decision_policy.py`)
- [x] Unknown material acquisition costs cannot silently become $0
- [x] Invalid financial inputs (NaN/Inf/negative/boolean-as-number) cannot produce BUY/STRONG BUY
- [x] Stripe webhook replay protection (timestamp tolerance)
- [x] Stripe webhook signature rotation (any valid v1 signature accepted)
- [x] Stripe refund accounting uses actual `amount_refunded`, not the `refunded` boolean
- [x] Webhook out-of-order updates cannot downgrade Refunded -> Paid
- [x] Category-mismatch detection fixed through the real normalize -> radar pipeline
- [x] SKU/listing-identity collisions removed (no `"CRTC-ITEM"` shared fallback)
- [x] Buyer-premium units standardized (percentage points vs. dollar amount)
- [ ] Webhook event-id idempotency wired into the live server path (`stripe_webhook_server.py`) — currently only Apps Script status-precedence protects production
- [ ] Dedicated security audit written up (`SECURITY_NOTES.md` — Session 7 of `CRTC_SESSION_PROMPTS.md` not yet done as a standalone artifact)

**Stage A status: NOT YET CLEAR.** The financial/webhook/category/SKU
hardening is done and tested; the remaining two boxes are process/audit
gaps, not known live bugs, but must be closed before calling Stage A done.

## Stage B — Friendly free beta (5–10 trusted resellers, target Oct 1 2026)

- [ ] Stage A fully clear
- [ ] Clear written usage limits for testers (single-workspace, estimates-only disclaimers per `CHATGPT_HANDOFF.md` section 8)

## Stage C — Wider free beta (invite link)

- [ ] Stage B clear
- [ ] Live Stripe Connect **test-mode** end-to-end run (OAuth -> pay -> refund -> webhook) with real deployment credentials
- [ ] Terms of Service + Privacy Policy (legal-reviewed, not just drafted)

## Stage D — Public store free listing

- [ ] Stage C clear
- [ ] Multi-tenant data isolation, OR a hard single-business mode enforced in code + UI
- [ ] Store submission assets complete and validated on the real toolchain per platform:
  - [ ] Android — built with real Gradle/Android SDK, installed on a physical device (`android/CRTC_PLAY_STORE_LAUNCH_PLAN.md`)
  - [ ] iOS — built with real Xcode/macOS, TestFlight smoke test passed (`ios/BUILD_CHECKLIST.md`)
  - [ ] Windows — built with real Visual Studio/MSIX tooling, package identity/signing verified (`windows/BUILD_CHECKLIST.md`)

## Stage E — Paid public

- [ ] Stage D clear
- [ ] Live Stripe Connect production approval
- [ ] Clean run history at Stage D scale

## Not a blocker (explicitly out of scope for launch gating)

- New source adapters beyond eBay
- Opportunity Radar arbitrary/fuzzy typo detection improvements beyond the existing dictionary-based check
- Pluggable payment processor beyond Stripe
- Bring-your-own Anthropic API key
