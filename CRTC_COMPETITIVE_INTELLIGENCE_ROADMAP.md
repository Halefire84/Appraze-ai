# CRTC Competitive Intelligence & Future Product Roadmap

**Research date:** 2026-09-20  
**Status:** RESEARCH / DEFERRED — do not implement roadmap items until current beta is stable and release-ready.  
**Primary repo:** Halefire84/Appraze-ai

## Executive finding

CRTC is **not alone** in combining resale sourcing, comps, demand and profit signals.

The closest newly identified competitor is **Scouted: Scan, Sell, Profit** (Velo Technologies), an iPhone app launched in June 2026. Its positioning is strikingly close to CRTC: scan an item, inspect recent sold comps, demand, sell-through, velocity, competition, ROI and a buy-under signal, then move toward listing. It currently has only 14 App Store ratings, so its market traction is not yet comparable with established crosslisting products. Scouted is currently iPhone-only and advertises a 7-day trial; US App Store in-app purchases shown are $7.99, $12.99 and $44.99 (the exact billing periods are not exposed in the indexed listing). 

Other meaningful adjacent competitors:
- **Thrift / ThriftMagic** — strong mobile eBay/resale valuation, sales-volume and sell-through workflow; 4.6/5 from ~1.1K App Store ratings.
- **What's it worth on eBay? / What's it worth?** — long-running eBay sold-price research tool; relaunched in 2026 with photo identification and sell-through statistics.
- **SellerAmp SAS** — Amazon-focused sourcing/profit-analysis analog with maximum-cost/ROI calculations.
- **Scoutly** — established barcode/database scouting workflow, primarily Amazon/book/media-oriented rather than CRTC's auction/estate/resale workflow.
- **Profit Finder** — focused eBay fee/profit calculator.
- **Vendoo, List Perfectly, Crosslist, PrimeLister, Flyp, SellRaze** — primarily downstream listing/crosslisting/automation competitors rather than direct buy-decision competitors.

## The strategic correction

Do **not** position CRTC as "the only app that does this."

Instead position it as:

> **A reseller's buy-to-profit operating system, with an auditable acquisition decision engine.**

The closest sourcing competitors validate the category. CRTC needs to differentiate on the depth and trustworthiness of the economics, especially for estate auctions, HiBid/CTBids, yard sales and thrift sourcing.

## Competitive map

| Competitor | Core strength | CRTC threat | CRTC opportunity |
|---|---|---|---|
| Scouted | Mobile sourcing intelligence, comps, demand, buy-under signal | **Very high** | Go deeper on true acquisition cost, auction lots, configurable rules, inventory-to-sale loop, auditability |
| Thrift/ThriftMagic | Fast eBay/resale valuation + volume/sell-through | High | Better fee-aware acquisition economics and auction modeling |
| What's it worth? | Long-running eBay sold research | Medium | Modern workflow, multi-market data, explicit BUY/PASS and acquisition economics |
| SellerAmp | Excellent sourcing/profit framework | Medium | Adapt the rigor to used goods, eBay and physical auctions instead of Amazon-only constraints |
| Scoutly | Fast barcode/database scouting | Medium | Photo-first, used-item, auction/thrift workflow |
| Profit Finder | eBay fee/profit math | Low/medium | Integrate calculator into the entire sourcing decision instead of a standalone calculator |
| Vendoo | Crosslisting/inventory | High downstream | Do not copy feature sprawl; make sync state verifiable |
| List Perfectly | Deep listing/inventory tooling | High downstream | Avoid complexity and subscription/add-on sprawl |
| Crosslist | Simple multi-marketplace publishing | High downstream | Master listing + marketplace-specific optimization + integrity verification |
| PrimeLister | Marketplace automation | Medium downstream | Safe, observable, reversible automation |
| Flyp | Low-cost crosslisting/automation | Medium downstream | Compete on profit generated, not lowest subscription |
| SellRaze | Photo/listing workflow | Medium | Reliability and economics first; AI listing generation is secondary |

## Newly identified direct/near-direct competitors

### 1. Scouted — highest-priority watch

Official site: https://scouted.live/

Current positioning:
- scan anything by camera/barcode
- recent sold comps
- active listings
- price bands
- platform breakdowns
- sell-through
- sales velocity
- competition
- ROI
- buy-under range
- sourcing lists
- one-tap listing
- authenticity analysis
- marketplaces including eBay, Mercari, Poshmark, Whatnot, TikTok Shop, Amazon and Facebook Marketplace

The App Store says the app is iPhone-only, launched June 2026, and currently has 14 ratings at 5.0. Its latest indexed release added faster/more resilient results, clearer sold/active data, improved sold-comp photos, authenticity analysis, a Finds tab and stability improvements.

**Important:** Scouted proves CRTC's concept has direct competition. It does not prove CRTC should abandon the concept. It means CRTC must differentiate around the acquisition/economic depth.

### 2. Thrift / ThriftMagic

App Store: 4.6/5, about 1.1K ratings.

Core features:
- scans resale marketplace listings
- estimates value
- daily/weekly/90-day sales volume
- eBay fee calculations
- bookshelf scanner
- sell-through rate
- barcode scanning

Recurring weaknesses visible in reviews:
- shelf scanner can be slow/inaccurate
- missed books/items
- occasional server overload
- reliability problems during periods of high load

**CRTC response:** never make scanner speed/AI identification more important than verified economics.

### 3. What's it worth on eBay?

Long-running product, now relaunched in 2026 as "What's it worth?"

Current Google Play listing says:
- sold-price research
- estimated price/shipping/net profit
- sell-through
- price distribution
- price trend
- condition filtering
- barcode and photo identification
- photo identification powered by Claude AI

The older App Store listing has 3.5/5 from 73 ratings and historical complaints about search accuracy, missing US results and lack of scanner/image detection. The 2026 Android relaunch is actively being updated.

**CRTC response:** treat valuation as an evidence engine, not a single estimated number.

### 4. SellerAmp SAS

Amazon-focused, but strategically important.

Its workflow includes:
- product identification
- historical sales/rank
- competing offers
- fees
- profit
- ROI
- break-even
- maximum cost to meet ROI/profit criteria
- sourcing history and organization

**This is the closest proven product pattern for CRTC's "maximum safe buy" concept.**

CRTC should borrow the *economic rigor*, not the Amazon-specific workflow.

### 5. Scoutly

Established barcode/database scouting product. Its current App Store history shows ongoing scanning, database-speed, camera-scanning and Bluetooth scanner improvements.

Strength:
- very fast sourcing/scanning workflow
- offline/database-oriented experience
- external Bluetooth scanner support

Weakness/opportunity:
- much more oriented toward barcode/database scouting than CRTC's photo-first used-goods + auction-lot workflow.

## CRTC's moat hypothesis

The defensible product loop should become:

FIND → IDENTIFY → SOLD COMPS → DEMAND → TRUE ACQUISITION COST → MAX SAFE BUY → BUY/PASS → INVENTORY → LIST → CROSSLIST → SELL → ACTUAL PROFIT → LEARN

The key is the **closed loop**.

A competitor can copy a calculator.
A competitor can copy AI listing generation.
A competitor can copy crosslisting.
A competitor can copy a BUY/PASS badge.

It is harder to replicate a trusted system that knows:
- what the item was expected to make
- what the user actually paid
- every acquisition cost
- where it was listed
- when it sold
- actual fees/shipping
- actual realized profit
- whether the original sourcing model was correct

## Deferred roadmap

### V1.0 — Public beta / launch hardening
**Target: Oct 1, 2026**
- Stabilize current feature set.
- Verify current deal dashboard.
- Verify 70%-of-value rule.
- Verify fee-aware profit math.
- Verify auction cost model.
- Verify sold comps.
- Verify inventory.
- Verify supplier tracking.
- Verify Stripe POS.
- Verify photo analyzer.
- Verify cross-list DRAFT generation.
- Security/reliability testing.
- No major new feature expansion.

**Exit condition:** current product works reliably enough for real beta users.

### V1.1 — Acquisition Intelligence
**Target: Oct 15, 2026**
- Maximum Safe Buy / Max Bid mode.
- Explicit cost-to-profit ladder.
- Confidence/evidence panel.
- Configurable acquisition rules.
- Preserve the existing 70% rule as a documented default, not hidden magic.

**Competitive answer:** Scouted + SellerAmp.

**Leapfrog:** make the number auditable from actual acquisition costs and fees, including auction premiums/tax/shipping.

### V1.2 — Demand Intelligence
**Target: Nov 1, 2026**
- Sell-through rate.
- Sales velocity.
- Active-vs-sold competition.
- Time-to-cash estimate.
- Condition-aware comp filtering.
- Demand confidence.

**Competitive answer:** Scouted + ThriftMagic + What's it worth?

**Leapfrog:** connect demand directly to the acquisition decision and capital-at-risk.

### V1.3 — Auction/Lot Intelligence
**Target: Dec 1, 2026**
- First-class auction LOT object.
- Allocate lot cost across items.
- Buyer premium/tax/shipping allocation.
- Lot-level projected profit.
- Lot-level BUY/PASS.
- Maximum total bid and per-item economics.

**Competitive answer:** the general sourcing category.

**Leapfrog:** specialize in estate-auction economics instead of treating every item as an isolated retail-arbitrage scan.

### V2.0 — Listing & Inventory Operating System
**Target: Jan 15, 2027**
- Canonical master listing.
- Marketplace-specific listing generation.
- Listing state machine.
- Marketplace sync state.
- Sync-health dashboard.
- eBay listing QA.
- Inventory aging.

**Competitive answer:** Vendoo / List Perfectly / Crosslist.

**Leapfrog:** verified state and integrity instead of blind "automation."

### V2.1 — Dead Money / Repricing
**Target: Feb 15, 2027**
- Inventory aging.
- Dead-stock alerts.
- Capital tied up.
- Economics-based repricing.
- Minimum profitable price.
- Markdown recommendations.

**Competitive answer:** downstream inventory competitors.

**Leapfrog:** every recommendation uses the user's actual cost basis.

### V2.2 — Local + Online Sales Unification
**Target: Mar 15, 2027**
- Stripe sale → inventory state.
- Local sale → online listing state.
- Delisting workflow.
- POS transaction reconciliation.
- Local-marketplace sales tracking.

**Competitive answer:** crosslisting/inventory systems.

**Leapfrog:** CRTC treats online and offline resale as one inventory system.

### V3.0 — Reseller Intelligence OS
**Target: Apr 15, 2027**
- Daily reseller brief.
- Portfolio-level capital allocation.
- Category/source performance.
- Supplier/source ROI.
- Predicted inventory risk.
- Actual-vs-projected deal accuracy.
- Personal sourcing history.
- "What should I buy more of?" insights.

**Moat:** CRTC learns from the user's actual outcomes.

## Features explicitly NOT prioritized

Do not build these merely because competitors have them:
- dozens of marketplace-specific automation bots
- massive feature-count parity
- complicated add-on subscription structures
- blind auto-delisting
- automation that cannot show its current state
- AI-generated copy without evidence
- vanity AI features
- marketplace integrations before core economics are reliable

## Competitive research cadence

Revisit competitors:
- monthly during 2026-2027 roadmap development
- immediately after a major competitor release
- before each CRTC major version
- whenever CRTC users report a competitor feature or complaint

Track:
1. New features
2. Pricing
3. App Store/Google Play ratings
4. Review complaints
5. Reddit/reseller-community complaints
6. Marketplace coverage
7. Sourcing accuracy
8. Crosslisting reliability
9. Data freshness
10. AI capabilities
11. User workflow
12. CRTC opportunity created by each weakness

## Product principle

**Current beta first. Roadmap second.**

No roadmap item should be implemented merely because it appears here. Each item becomes active only when the current release is stable, tested, and the feature has a clear measurable reason to exist.

## Research sources checked on 2026-09-20

- Scouted official site: https://scouted.live/
- Scouted App Store listing
- Thrift/ThriftMagic App Store listing and reviews
- What's it worth on eBay / What's it worth Google Play and App Store listings/reviews
- SellerAmp SAS App Store listing
- Scoutly App Store listing
- Profit Finder App Store listing
- Prior competitive research covering Vendoo, List Perfectly, Crosslist, PrimeLister, Flyp and SellRaze

This document is a living competitive/roadmap reference, not a commitment that every feature will ship on the listed date.


## Product Expansion Architecture — Added 2026-09-20

The roadmap is intentionally divided into **CRTC Core**, **CRTC Intelligence**, and **Future Expansion / Possible Separate Products**. Deferred ideas are not rejected; they are parked until real user behavior and product data show whether they belong in CRTC, should become an optional module, or deserve a separate product.

### CRTC Core — The Money Engine

The core product should remain focused on the reseller's economic loop:

FIND → IDENTIFY → SOLD COMPS → DEMAND → TRUE ACQUISITION COST → EXPECTED NET → ROI → MAX SAFE BUY → BUY/PASS → INVENTORY → LIST → SELL → ACTUAL PROFIT

Core capabilities:
- Item identification and evidence-backed comps
- Demand/sell-through signals
- True acquisition-cost calculation
- Fee, tax, premium and shipping modeling
- Maximum Safe Buy / Maximum Bid
- BUY/PASS decision with auditable reasoning
- Inventory and cost basis
- Listing creation and crosslisting drafts
- Actual sale and realized-profit tracking

### CRTC Operating System — Later Core Expansion

Once the money engine is stable:
- Verified marketplace states
- Inventory aging
- Dead-money detection
- Repricing and minimum-profitable-price logic
- Local + online sales unification
- Source/supplier performance
- Capital allocation
- Personal sourcing history
- Actual-vs-projected deal accuracy

### CRTC Intelligence Layer — Later

Use accumulated real-world outcomes to add:
- Daily reseller brief
- Category profitability intelligence
- Source profitability intelligence
- Personalized sourcing recommendations
- Deal-history learning
- Inventory-risk forecasting
- Portfolio-level reseller analytics
- "What should I buy more of?" insights

These recommendations must be based on evidence and the user's actual results, not unexplained AI guesses.

## Future Expansion / Possible Separate Products

The following ideas remain intentionally parked rather than deleted:

### Marketplace Automation
- Advanced marketplace-specific automation
- Poshmark-style engagement automation
- Follow/share/relist automation
- Advanced marketplace task scheduling
- Broader marketplace integrations

### Business Operations
- Marketing automation
- Customer CRM
- Advanced shipping management
- Accounting/bookkeeping
- Advanced supplier management
- Team/employee workflows
- Multi-user business management
- Enterprise features

### AI Workforce
Potential future agent capabilities:
- Autonomous listing agent
- Autonomous sourcing/research agent
- Inventory-management agent
- Pricing/repricing agent
- Customer-response agent
- Business reporting agent
- Workflow orchestration across reseller tools

These capabilities should only be added when their reliability, permissions, observability and reversibility are production-ready.

## Feature Decision Rule

Every future feature must answer at least one of these questions:

1. Does it help the reseller make a better buying decision?
2. Does it protect or increase margin?
3. Does it help move inventory?
4. Does it improve understanding of actual profit?
5. Does it create trustworthy learning from real outcomes?

If the answer is no, the feature should normally remain deferred.

A feature should **not** be added solely because a competitor has it.

## Do Not Delete — Reclassify

When an existing CRTC feature does not fit the immediate core:
- Do not casually delete it.
- Identify dependencies and current usage.
- Determine whether it supports the core indirectly.
- Consolidate duplicate functionality where appropriate.
- Move experimental or low-priority capabilities into the future roadmap when useful.
- Preserve functionality unless there is a clear technical or product reason to remove it.
- Document any removal or consolidation.

The objective is to reduce **current product complexity**, not reduce the long-term vision.

## Future Product Boundary

A deferred capability may eventually become:
1. A normal CRTC feature,
2. An optional CRTC module,
3. An agent/workflow add-on, or
4. A separate product/company opportunity.

That decision should be made from evidence: user demand, usage frequency, technical complexity, reliability requirements, monetization potential and whether the capability distracts from the core buy-to-profit loop.

**Guiding principle: Do not shrink the vision. Shrink the immediate scope.**

