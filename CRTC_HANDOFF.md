# CRTC — Project Handoff Point

**Canonical repository:** Halefire84/Appraze-ai
**Product direction:** CRTC (Cooper River Trading Co.)
**Last handoff:** 2026-09-09

## Current state
- Appraze repository remains the canonical codebase; do NOT start a replacement app/repository.
- Opportunity Radar backend exists in `opportunity_radar.py`.
- Opportunity Radar tests exist in `tests/test_opportunity_radar.py`.
- Streamlit page exists at `pages/1_🔎_Opportunity_Radar.py`.
- Existing eBay Browse API adapter can retrieve active listings through the official API.
- Existing comps architecture distinguishes active asking prices from sold/completed-sale evidence.

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

## Next implementation target
Connect the Opportunity Radar to the existing legitimate marketplace acquisition layer, beginning with eBay Browse API results. Preserve source URLs and listing metadata, normalize records into the Radar schema, score/rank them, and present the highest-priority candidates.

Then connect promising candidates to the existing valuation/comps and CRTC verdict workflow.

## Guardrails
- Do not build anti-bot bypasses or evasion tooling.
- Prefer official APIs, permitted feeds, exports, and user-supplied data.
- Radar scores are leads, not proof. Authenticity, condition, sold comps, fees, shipping, and category must be verified before a purchase decision.
- Preserve the existing application architecture and tests.
- Avoid duplicating the valuation/verdict engines when existing modules can be reused.

## Naming direction
Use **CRTC** as the product-facing name going forward. The GitHub repository name may remain `Appraze-ai` until a deliberate repository rename is made. Do not rename files or break imports merely for branding.

## Handoff instruction
If context/usage runs out, resume from this document. First inspect the current repository state and recent commits, then continue with the "Next implementation target" above. Do not rebuild prior work.
