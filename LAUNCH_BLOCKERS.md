# CRTC Launch Blockers

Hard gates only — not a general TODO list. See `CRTC_HANDOFF.md` for full
implementation detail and `CHATGPT_HANDOFF.md` / `CRTC_SESSION_PROMPTS.md`
for the hardening-session history behind these items.

Last verified: 2026-09-22 — `python3 -m pytest tests/ -q` -> 497 passed, 0 failed.

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
- [x] Webhook event-id idempotency wired into the live server path (`stripe_webhook_server.py`) — done 2026-09-21/22, a Stripe event id is persisted on the sales_log row itself (`_last_event_id`), durable across process restarts, not just an in-memory set
- [x] Invite-code-gated beta signup — closes the open-signup/unlimited-free-AI-quota abuse vector (`CRTC_BETA_INVITE_CODES`)
- [x] Brute-force login lockout (5 attempts / 15 min) on Admin, tester, and beta-account logins
- [x] Stripe payment-session replay across accounts closed (`RedeemedStripeSessions` in AppsScript_Code.gs)
- [x] Arbitrary Google Drive file exposure via `scan_folder` closed (`ALLOWED_SCAN_FOLDER_NAMES` allowlist)
- [x] Spreadsheet formula/CSV injection via display_name defused
- [x] Timing-unsafe secret comparisons (token, admin invite code) replaced with constant-time compare
- [x] Escalating abuse-detection lockout (temp lockout -> permanent/admin-required after repeated bot-like abuse) — done 2026-09-22, `checkAndRecordAbuseAttempt_` in `AppsScript_Code.gs`, gates `reserve_ai_usage`
- [ ] Dedicated security audit written up (`SECURITY_NOTES.md` — Session 7 of `CRTC_SESSION_PROMPTS.md` not yet done as a standalone artifact); a real audit pass happened 2026-09-22 (see `.agent/HANDOFF.md`) but hasn't been written up as its own document

**Stage A status: CLOSE.** The financial/webhook/category/SKU/auth/abuse
hardening is done and tested. The remaining gap is writing up the
2026-09-22 security-audit findings as a standalone `SECURITY_NOTES.md`.

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
