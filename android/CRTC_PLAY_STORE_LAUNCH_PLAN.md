# CRTC Android / Google Play Launch Plan

## Target
Ship CRTC as a polished Android app backed by the existing CRTC web application and hunting backend.

## Important Google requirement
For a new personal developer account created after November 13, 2023, Google Play requires a closed test with at least 12 testers continuously opted in for at least 14 days before production access can be requested.

## Practical launch schedule
### Phase 1 — Android shell + mobile UX
Target: 3–5 days
- Create Android package/application ID.
- Mobile-first CRTC home screen.
- One-tap HUNT NOW.
- Holy Grail results.
- Analyzer/photo entry.
- Account/auth handoff.
- External web/backend connection to the current Streamlit deployment.

### Phase 2 — Real-device QA
Target: 2–4 days
- Pixel/Android testing.
- Login.
- Hunt flow.
- Analyzer.
- Pricing page.
- Payment handoff.
- Deep links.
- Offline/error states.
- Privacy/security review.

### Phase 3 — Google Play closed test
Minimum: 14 continuous days with 12 opted-in testers for a new personal account.
Recommended: recruit 15–20 testers so the project does not fail the minimum if someone drops out.

### Phase 4 — Production submission
After the closed-test requirement is satisfied:
- Complete Play Console production access questionnaire.
- Upload final Android App Bundle.
- Complete store listing, privacy policy, data safety, content rating and screenshots.
- Submit for production review.

## Realistic expectation
If the Android shell and store assets are ready quickly, the technical build can be ready in roughly 1–2 weeks. The Google Play closed-test requirement means a new personal account puts the realistic public-launch window at roughly 2–4 weeks from the start of the Android build, plus any review/setup delay.

## Monetization
The first public Android release should use the CRTC web billing architecture already in the repository rather than inventing a second pricing system. Subscription/payment configuration must be completed and tested before charging customers.

## Launch positioning
**CRTC — Don't search harder. Let CRTC find what everyone else missed.**

Primary feature: Opportunity Intelligence / Holy Grail Finder.
Secondary features: listing analysis, valuation, max-bid math, liquidation/surplus analysis, inventory and financial intelligence.
