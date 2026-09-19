# CRTC Gap Closure Report — 2026-09-19

The authoritative P0 source tree was hardened locally from CRTC-P0-hardened.zip.

## Closed in the working tree

- Restored missing valuation_bridge.py and routed valuation through decision_policy.
- Restored missing webhook_store.py persistence client.
- Removed duplicate auction BUY/PASS math from auction_radar.py; it now consumes the canonical decision result.
- Normalized buyer_premium through number_normalize in listing_normalizer.py.
- Added conservative fuzzy high-value brand typo detection and regression coverage.
- Added explicit tester workspace identity and opt-in tester authentication.
- Added login/signup attempt rate limiting.
- Changed Apps Script tenancy resolution so client-supplied is_admin flags are not trusted; admin status is resolved from the Users sheet.
- Added beta Terms of Service and Privacy Policy drafts.
- Added Stripe Connect test-mode E2E runbook.
- Added LAUNCH_BLOCKERS.md with the remaining external release gates.
- Removed stale demo-mode claims from authentication/release documentation.

## Verification

Required P0 suite:
19 passed in 0.07s

Related suite:
88 passed in 0.22s

Gap-closure pure suite:
26 passed in 0.15s

Full pytest suite in the development container, using a test-only Streamlit stub because Streamlit is not installed in this execution environment:
263 passed, 9 warnings in 0.81s

Python compileall:
OK

## External gates that cannot honestly be marked complete from source code alone

- Real Stripe Connect test-mode OAuth/payment/refund/webhook E2E with deployment credentials.
- Legal review of the beta Terms of Service and Privacy Policy.
- Production credential rotation/redeployment.

The full fixed working tree is packaged as CRTC-gap-closure-2026-09-19.zip. The GitHub default branch currently contains the handoff/report documentation but not the complete P0 source tree, so this report deliberately does not claim that the entire source tree has been pushed there.
