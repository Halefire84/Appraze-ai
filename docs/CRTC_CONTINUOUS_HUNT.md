# CRTC Continuous Hunt

CRTC now has a controlled evolution loop:

1. **Discovery** — scheduled last-chance eBay auction scans.
2. **Opportunity scoring** — the existing Holy Grail radar ranks information-failure patterns.
3. **Outcome learning** — `crtc_learning.py` records BUY/PASS outcomes and realized profit.
4. **Optimization** — signal performance can be measured before changing production rules.
5. **Safety gate** — production scoring is not rewritten automatically; changes should be tested first.

## Scheduled worker

`.github/workflows/crtc-hunt.yml` runs every 15 minutes and can also be started manually. GitHub supports scheduled workflows as frequently as every five minutes, but CRTC deliberately uses a 15-minute cadence to reduce API pressure and scheduling contention.

The worker currently automates **eBay only**, using the official Browse API and auction-only filtering. CTBids, ShopGoodwill, and other sources remain in the source registry until a legitimate API/feed/public access path is confirmed. No anti-bot bypass or stealth scraping is used.

## GitHub secrets required for the worker

Add these repository Actions secrets:

- `EBAY_CLIENT_ID`
- `EBAY_CLIENT_SECRET`

These are separate from Streamlit Cloud secrets. The worker uploads each hunt result as a GitHub Actions artifact for 14 days.

## Learning records

The learning module uses JSONL so each outcome is append-only and easy to inspect. Example:

```python
from crtc_learning import OpportunityOutcome, append_outcome

append_outcome(OpportunityOutcome(
    listing_id="...",
    source="eBay",
    title="...",
    predicted_score=91,
    predicted_value=350,
    max_buy=100,
    decision="BUY",
    acquisition_cost=72,
    resale_price=310,
    signal_codes=["weak_title", "photo_dependent_listing"],
))
```

The long-term goal is to learn which signals actually predict profitable outcomes for CRTC rather than assuming every high score is good.

## Android

The current Streamlit deployment is the fastest Android path. On the Pixel 6:

1. Open the CRTC Streamlit URL in Chrome.
2. Sign in normally.
3. Tap Chrome's three-dot menu.
4. Choose **Add to Home screen** (wording can vary by Chrome version).
5. Name the shortcut **CRTC**.
6. Put it on the first home-screen page.

This provides one-tap access while the backend remains in the cloud. A native Android wrapper/PWA can be added later if it materially improves camera, notifications, or offline behavior.
