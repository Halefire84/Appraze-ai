# Appraze — Dominance Roadmap

_Proposal, not yet built. Per the P0-first / no-feature-creep direction
this repo has followed all along, nothing here ships until it's picked
and the P0/auth-gate items already flagged in `LAUNCH_CHECKLIST.md` are
closed. This is Phase 2 (design) — Phase 3 (build) is deliberately
deferred to a session where you've picked which of these you actually
want, rather than three major features going in unreviewed._

Grounded in `COMPETITIVE-GAPS.md`'s research: every competitor found is
**post-purchase** (list/track/analyze what you already own). Nothing
found helps decide whether to buy *before* money changes hands. Every
proposal below leans into that gap rather than copying a crosslisting
feature some other tool already does adequately.

## Fastest wins first — already built, tested, just not wired in

Before any "10x" feature: this repo already contains real, tested code
for several of the ideas below that simply isn't connected to anything.
Wiring these is lower-risk than building new and should happen
regardless of which big feature gets picked next:

| Module | What it already does | What's missing |
|---|---|---|
| `crtc_learning.py` | Outcome-tracking/learning-loop logic, tested | Not wired into Opportunity Radar — see `docs/CRTC_CONTINUOUS_HUNT.md` |
| `ebay_image_scan.py` | Hardened eBay search-by-image adapter, tested | Not called from any page |
| `mail.py` / `mail_parse.py` + `drive_scan.py` | Read-only supplier-invoice tracking (IMAP + Drive), tested | No Mail tab exists in the app |

## Proposed differentiators

### 1. Outcome Learning Loop — "the more you sell, the smarter it gets"

**Pain it kills:** Every verdict today is a one-time estimate with no
memory. A reseller has no way to know if Appraze's BUY calls actually
paid off, and Appraize has no way to get better at calling them.

**How it's measured:** Prediction-vs-actual accuracy (predicted profit/
ROI/sale price vs. realized, once an item sells) tracked over time,
surfaced as a real number on a dashboard — not a vague "AI learns from
you" claim.

**Build order:** (1) wire `crtc_learning.py` into the flip lifecycle so
every sold item records predicted-vs-actual; (2) add a simple accuracy
dashboard; (3) feed accuracy trends back into `decision_policy.py`'s
confidence scoring, so confidence isn't just about comps quality but
about "how often has Appraize been right for items like this."

**Which competitor it buries:** None of the 7 researched offer this at
all — sellerboard tracks profit after the fact but never checks its own
predictions against outcomes; nothing else in the category makes a
prediction to check in the first place.

**Why it's #1:** Lowest risk (code exists, tested), compounds forever,
and it's the one feature that makes every other feature on this list
get better over time instead of staying static.

### 2. Photo-to-Verdict Loop

**Pain it kills:** Standing at an estate sale, a reseller today has to
type item details by hand before getting any verdict. Every second
spent typing is a second a faster competitor could out-bid you on the
same lot.

**How it's measured:** Time from photo taken to verdict shown, target
under 10 seconds; compare against the current manual-entry flow's timed
baseline (see Speed item below — measure both from the same session).

**Build order:** (1) wire `ebay_image_scan.py` into `comps.py`'s
existing distribution-stats valuation so a photo produces real comps,
not a guess; (2) feed that straight into `decision_policy.py`'s
`evaluate_deal()` for an immediate verdict; (3) surface confidence
explicitly when image identification itself is uncertain — never let a
shaky photo match produce a confident-looking BUY.

**Which competitor it buries:** SellRaze gets closest (photo → listing
draft), but that's photo-to-*listing*, for an item already owned — not
photo-to-*buy verdict*, before money changes hands. This is a different
category, not a faster version of their feature.

### 3. Probabilistic Profit Distributions

**Pain it kills:** A single verdict number ("BUY, 47% ROI") hides real
uncertainty. Two items with identical point estimates can have wildly
different risk — one backed by 20 tight comps, one by 2 scattered ones
— and today's verdict looks the same either way.

**How it's measured:** Show a range (e.g. "60% chance of 30-50% ROI, 15%
chance of a loss") instead of one number, and — once the Outcome
Learning Loop above is live — validate that items marked "high
confidence" actually land in their predicted range more often than
"low confidence" ones. That validation step is what makes this real
instead of decorative.

**Build order:** (1) `comps.py` already computes distribution stats from
comparable listings — extend that into a profit-outcome distribution
rather than a single confidence label; (2) surface it as a range in the
UI, not a chart for its own sake; (3) only after the Learning Loop
exists to check it against reality.

**Which competitor it buries:** Every competitor researched — and most
of the wider resale-tool market — presents a single number or a flat
confidence label. Modeling uncertainty explicitly, and then proving the
model is calibrated against real outcomes, is not something a
crosslisting tool has any reason to build; it only matters to a tool
whose job is the buy decision itself.

### 4. Estate-Sale Field Mode (larger, Phase 4 candidate)

**Pain it kills:** The whole app currently assumes a decent connection
and a comfortable typing session. An estate sale or auction preview is
neither — spotty wifi, one hand full, a line of other buyers already
looking at the same lot.

**How it's measured:** Taps-to-log-an-item, and whether the flow
survives a dropped connection without losing data (sync-on-reconnect,
not sync-or-lose-it).

**Why Phase 4, not now:** Real offline support is a different technical
problem for a Streamlit web app than anything else on this list — it
needs local-first storage and conflict resolution on reconnect, not
just a faster UI. Worth doing, not worth rushing alongside the three
above.

### 5. AI Sourcing Agent (larger, Phase 4 candidate)

**Pain it kills:** Opportunity Radar and Auction Hunt already scan for
mispriced listings, but today the reseller has to open the app and hit
refresh. A genuinely proactive agent would push an alert the moment a
matching listing appears, before a competitor sees it.

**Why Phase 4, not now:** Continuous background scanning with push
notifications needs a always-on scheduler/service, not just app code —
real infrastructure, real ongoing cost, and it should be built once the
scanning logic underneath it (already in `auction_radar.py` /
`opportunity_sources.py`) has more real-world mileage behind it.

## Recommendation

Build, in order: **Outcome Learning Loop → Photo-to-Verdict Loop →
Probabilistic Profit Distributions.** All three lean on code that
already exists and is tested, all three compound rather than sitting
static, and together they're the difference between "another verdict
calculator" and a system that gets measurably better the more it's
used — which is the one thing in `COMPETITIVE-GAPS.md`'s research no
competitor is doing at all. Estate-Sale Field Mode and the AI Sourcing
Agent are real, worth doing, and deliberately queued behind these three.
