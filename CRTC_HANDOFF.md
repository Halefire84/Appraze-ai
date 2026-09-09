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
- New `listing_normalizer.py` converts source-specific records into the common CRTC listing schema.
- New `tests/test_listing_normalizer.py` covers alias handling, metadata preservation, and batch normalization.
- New `source_registry.py` contains the expandable legitimate-source registry, with eBay currently the only automated source enabled by default.
- New `tests/test_source_registry.py` covers registry behavior and safe source onboarding.

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

## Holy Grail multi-source discovery
CRTC should NOT depend on one marketplace. Build the acquisition layer as a pluggable source registry so new legitimate sources can be added without changing the Radar/scoring engine.

### Priority source groups
1. **Core resale marketplaces / auction platforms**
   - eBay
   - HiBid
   - Proxibid
   - LiveAuctioneers
   - Invaluable
   - AuctionZip / auctioneer discovery
   - Everything But The House (EBTH)
   - MaxSold
   - CTBids / Estate Auctions
   - ShopGoodwill / Goodwill auctions

2. **Government, municipal, police and institutional surplus**
   - GSA Auctions
   - GovDeals
   - Public Surplus
   - GovPlanet
   - PropertyRoom
   - Municibid
   - Purple Wave
   - state/local government surplus portals
   - police/seized-property auctions
   - school, university, airport, hospital and other institutional surplus auctions

3. **Local and regional auction houses**
   - independent online-only estate auctions
   - estate-liquidation companies
   - bankruptcy and business-liquidation auctions
   - industrial/equipment auctions
   - farm and construction auctions
   - storage-unit / abandoned-property auctions where legally accessible
   - local auctioneer catalogs and directories

4. **Specialty opportunity sources to evaluate**
   - storage/locker auction platforms
   - retail returns/liquidation marketplaces
   - commercial liquidation platforms
   - jewelry/watch/coin specialty auctions
   - vintage/collectibles specialty auctions
   - regional charity/thrift auctions

### Source discovery rule
The source list is intentionally expandable. CRTC should maintain a source registry with fields such as:
- source name
- source type/category
- geographic coverage
- acquisition method (official API, permitted feed/export, public catalog, user-provided data, etc.)
- active/sold evidence capability
- category coverage
- source URL
- rate/usage limits
- terms/compliance notes
- enabled/disabled status

CRTC should periodically identify additional legitimate auction platforms and regional sources that are likely to contain resale opportunities, then add them through adapters rather than hard-coding source-specific logic into the Radar.

Do not treat an aggregator as the authoritative source when the original auction listing is available. Preserve the original auction URL and source identity so the user can verify the lot and bid directly.

## Holy Grail detection across sources
Every source should be transformed into a common listing schema before scoring. The normalized record should preserve, when available:
- source and source listing ID
- original URL
- title
- description
- category
- asking/current bid price
- auction end time
- seller/auctioneer identity
- location and pickup/shipping information
- buyer premium and known fees
- images/image URLs when permitted
- condition
- lot number
- estimated value / market evidence

Radar should then look for the same anomaly classes across every source: typos, weak metadata, title/description contradictions, category errors, suspiciously low prices, incomplete brand/model identifiers, and combinations of weak signals. It should also learn source-specific patterns without changing the core scoring contract.

## Next implementation target
1. Connect the existing eBay Browse acquisition to `listing_normalizer.py`, preserving the richer listing fields instead of reducing everything immediately to `Comp` objects.
2. Feed normalized eBay records into Opportunity Radar and rank the live candidates while preserving original listing URLs.
3. Add a dedicated CRTC opportunity result model/UI that separates Radar lead score from market-value confidence and eventual BUY/PASS.
4. Add source adapters incrementally, prioritizing CTBids/Estate Auctions, ShopGoodwill, HiBid, and other sources where legitimate acquisition is available.
5. Connect promising candidates to the existing valuation/comps and CRTC verdict workflow.

## Guardrails
- Do not build anti-bot bypasses or evasion tooling.
- Prefer official APIs, permitted feeds, exports, public catalogs where permitted, and user-supplied data.
- Respect each source's terms, robots/access controls, rate limits, authentication requirements, and licensing restrictions.
- Radar scores are leads, not proof. Authenticity, condition, sold comps, fees, shipping, pickup costs, and category must be verified before a purchase decision.
- Preserve the existing application architecture and tests.
- Avoid duplicating the valuation/verdict engines when existing modules can be reused.

## Naming direction
Use **CRTC** as the product-facing name going forward. The GitHub repository name may remain `Appraze-ai` until a deliberate repository rename is made. Do not rename files or break imports merely for branding.

## Handoff instruction
If context/usage runs out, resume from this document. First inspect the current repository state and recent commits, then continue with the numbered "Next implementation target" above. Do not rebuild prior work.
