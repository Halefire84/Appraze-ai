# CRTC Flip Lifecycle

CRTC now treats a resale opportunity as a lifecycle rather than a one-time verdict:

`FIND → IDENTIFY → VALUE → DECIDE → BUY → TRACK → LIST → SELL → MEASURE`

## Canonical flow

1. **FIND** — Opportunity Radar and permitted auction catalog imports discover leads.
2. **VALUE** — Market evidence is kept separate from Radar discovery signals.
3. **DECIDE** — Canonical CRTC BUY / PASS / BORDERLINE / REVIEW decision.
4. **BUY** — Only an explicit BUY decision can create inventory intake.
5. **TRACK** — `flip_ledger.py` creates a canonical flip record with a settled cost basis.
6. **LIST** — Record the intended list price and marketplace fee assumption.
7. **SELL** — Record actual sale price and outbound shipping.
8. **MEASURE** — Realized net proceeds, profit, margin and ROI are calculated from actual sale economics.

## Evidence and cost rules

- Auction buyer premiums are not invented when unknown.
- Active asking prices are not relabeled as sold evidence.
- Marketplace publishing remains an integration layer; the ledger does not pretend to publish listings.
- Profit is based on settled acquisition cost, not the original auction hammer price.
- A zero-cost profitable item reports infinite ROI rather than dividing by zero.

## Persistence

The Flip Ledger uses the existing `storage.py` named-table interface with the `flip_ledger` table. It therefore follows the repository's existing per-user/admin-shared storage model rather than creating a second database.
