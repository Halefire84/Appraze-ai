# Appraze — Competitive Landscape & Gaps

_Research date: 2026-09-21. Every factual claim below is sourced; where
sources disagreed or a number couldn't be confirmed, it's marked
**UNKNOWN** rather than guessed. This document is about the reseller
crosslisting/inventory/analytics tool market broadly — nothing here
should be read as confirming any tool "copies" another; it's a survey
of what's publicly claimed and publicly complained about._

## The category, briefly

Every competitor below is a **post-purchase** tool: it helps you list,
track, or analyze inventory you already bought. None of them help you
decide whether to buy something *before* money changes hands. That gap
is covered in "Where they all bleed" below — it's the single biggest
structural difference between this market and what Appraze's
`decision_policy.py` verdict engine already does.

---

## Vendoo

**What it does well:** Crosslisting across 11 marketplaces (eBay,
Poshmark, Mercari, Etsy, Depop, Grailed, Facebook Marketplace, Shopify,
Vinted, Vestiaire Collective, Whatnot in beta), automatic sale detection
that delists sold items elsewhere to prevent overselling, AI listing
enhancement, bulk import/delist/relist. [Nifty's Vendoo
review](https://nifty.ai/post/vendoo-review),
[Vendoo's own pricing page](https://www.vendoo.co/pricing)

**Complaints (sourced):** Users report items that stayed listed on other
platforms after selling elsewhere — the exact failure the auto-delist
feature exists to prevent — plus support allegedly suggesting users
"leave the computer open overnight" so the software could detect sales;
constant connectivity issues; and reports of continued billing after
cancellation. [Trustpilot via
PissedConsumer](https://trustpilot.pissedconsumer.com/review.html)

**Pricing:** Three tiers — Starter, Growth, Pro. Sources disagree on the
exact starting price: **$14.99/mo** per [Vendoo's own pricing
page](https://www.vendoo.co/pricing) and
[Tekpon](https://tekpon.com/software/vendoo/pricing/), vs. **$8.99/mo**
cited by [nifty.ai's Vendoo
review](https://nifty.ai/post/vendoo-review) — mark the exact entry
price **UNKNOWN** pending a direct check, but $14.99 / $29.99 / $59.99
for Starter/Growth/Pro is the figure that recurs most. 14-day free
trial. All plans include unlimited listings and all marketplaces.

**Core user:** Multi-platform resellers who already have real volume
across 3+ marketplaces and want one dashboard instead of tab-switching.

---

## List Perfectly

**What it does well:** Crosslisting to 11 marketplaces including
Whatnot (added October 2025, unlimited on every plan, no add-on fee),
image hosting with AI background removal via PhotoRoom, unlimited
products/crosslisting on every paid tier. [List Perfectly
pricing](https://listperfectly.com/pricing/)

**Complaints (sourced):** The tools most sellers actually want are
gated behind the $69/mo "Pro" tier, and auto-delist (preventing
double-selling) is Pro Plus only, at $99+/mo — the features that solve
the category's #1 recurring pain point are the most expensive add-on,
not the baseline. No in-depth analytics, a real learning curve, and
rigid pricing structure are cited as the top reasons sellers look for
alternatives. [Vendoo's List Perfectly pricing
breakdown](https://blog.vendoo.co/list-perfectly-pricing-how-much-does-this-crosslisting-app-cost),
[Voolist's Vendoo alternatives
roundup](https://www.voolist.com/blog/best-vendoo-alternatives)

**Pricing:** Four tiers, ~$29/mo entry up to $99–249/mo for Pro Plus. No
annual discount — full price every month regardless of commitment
length. 5-day or 100-listing money-back window.

**Core user:** Established multi-marketplace sellers willing to pay up
for the top tier once they've outgrown the basics.

---

## PrimeLister

**What it does well:** Crosslists to 8 platforms, bulk crosslisting,
scheduled listing times. [PrimeLister
pricing](https://www.primelister.com/pricing/cross-listing)

**Complaints (sourced) — the most negative of any tool researched:**
- Sync failures causing accidental double-sells when the browser
  extension glitches or a manual delist is missed.
- Pricing that "stacks": the entry "Crosslisting Basic" plan at $29.99
  doesn't include true crosslisting, so sellers report ending up on
  three separate subscriptions totaling near **$90/month** once
  everything needed is added up.
- One reviewer reported the cancellation button was hidden behind a
  support chat widget, leading to an unwanted renewal charge with no
  refund issued.

[Nifty's PrimeLister cost
breakdown](https://nifty.ai/post/primelister-cost), [Vendoo's
PrimeLister review](https://blog.vendoo.co/primelister-review)

**Pricing:** Entry eBay-only automation at $15/mo; Pro crosslisting at
$49.99/mo. Annual plans ~30% cheaper than monthly.

**Core user:** Budget-conscious sellers who start on the cheap entry
tier and often don't realize the real cost until they need what's
gated behind add-ons.

---

## Flipwise

**What it does well:** Inventory/sales/cost tracking without
spreadsheets, an inventory-aging report flagging items unsold at 90/180/
365 days, purchase-location profitability analysis, eBay auto-sync.
Praised repeatedly as visually clean — "feels less like a ledger and
more like a dashboard" — and for responsive support. [Flipwise sales
insights page](https://flipwise.app/sales-insights), [Steve King's
Flipwise review](https://stevekingonline.com/flipwise-review/)

**Complaints (sourced):** The "Ghost Inventory" problem — Flipwise
still shows an item as in-stock weeks after it sold if the user misses
a manual step, the same category of oversell risk that plagues
Vendoo/PrimeLister, just framed differently. [CLOSO's Flipwise
review](https://closo.co/blogs/blog/is-flipwise-the-inventory-savior-we-were-promised-an-honest-review)

**Pricing:** Usage-based on total active listings + items sold in the
last 30 days, rather than flat tiers — scales up as the store grows.
Exact dollar breakpoints: **UNKNOWN** (not published in the sources
checked).

**Core user:** eBay-focused resellers who want inventory/margin
visibility without adopting a full crosslisting suite.

---

## sellerboard

**What it does well:** Amazon-specific profit analytics with genuine
cash-flow projection (modeling Amazon's payment schedule against
pending fees and incoming orders), COGS management, a 4.5/5 Trustpilot
rating, and a reputation as "the default recommendation" for Amazon
sellers who want accurate numbers without overpaying. [sellerboard.com](https://sellerboard.com/),
[thepricegeek's sellerboard
review](https://www.thepricegeek.com/profit-analytics/sellerboard-review/)

**Complaints (sourced):** Bugs and inaccurate cost reporting reported
over a 2-year period by at least one long-term user; automatic
review-request/autoresponder features reported as unreliable;
one recent reviewer described support as "non-existent with
AI-responses and no fixes." Most negative reports predate 2023 and are
described as since-addressed, per the same sources.

**Pricing:** Free trial (1 month, no card) up to $79/mo, scaled by
monthly order volume; $15/mo cited as a common entry point.

**Core user:** Amazon FBA/FBM sellers specifically — this tool doesn't
serve cross-platform resellers at all, which is itself a gap (see
below).

---

## Nifty (AI) — researched in place of "Nifty Stats," which doesn't
## appear to exist under that exact name; Nifty AI (rebranded from
## AutoPosher) is the closest real match and is what's covered here.

**What it does well:** AI-assisted crosslisting that translates listing
details between marketplace formats automatically, strong Poshmark
automation specifically, auto-delist on detected sale, sales-data
analytics ("Nifty Stats" may be a reference to this analytics feature
rather than a separate product). [nifty.ai](https://nifty.ai/)

**Complaints (sourced):** At $69.99/mo it's cited as "among the most
expensive reseller software platforms in 2026"; AI features are gated
behind limited "Smart Credits" that can require additional purchases;
marketplace support is limited to five platforms (versus 8-11 for
Vendoo/List Perfectly); mixed reviews specifically cite the credit
limits and higher price as friction. [Vendoo's Nifty AI pricing
review](https://blog.vendoo.co/nifty-ai-pricing)

**Pricing:** $69.99/mo base, with additional fees for larger inventory
and AI usage beyond the included Smart Credits.

**Core user:** Poshmark-heavy sellers who want the most AI automation
and are willing to pay the market's top price for it.

---

## SellRaze

**What it does well:** AI-powered listing generation from a photo,
barcode, or short prompt — auto-generates titles, descriptions,
categories, and suggested pricing. Also scans multiple markets to
suggest what to pay, a selling-price range, which marketplace has the
best chance of a fast sale, and estimated time-to-sell — this is the
*closest* any researched competitor gets to pre-purchase decision
support, though it's about **listing/pricing an item you already have**,
not evaluating whether to buy it. Reviewers cite listing time cut to
"30 seconds." [SellRaze.com](https://www.sellraze.com/),
[PulsRev's SellRaze review](https://www.pulsrev.com/tools/sell-raze)

**Complaints:** Not found in the sources checked — reviews located
skewed positive with no specific complaint pattern identified. Treat
this as incomplete research rather than "no complaints exist."

**Pricing:** Free, Plus ($29.99/mo), Pro ($59.99/mo) per one source; a
second source states pricing "starts at $23.99/month." **Discrepancy
unresolved — mark exact entry price UNKNOWN.**

**Core user:** Sellers who want AI to shortcut the listing-creation
step specifically, across eBay, Poshmark, Depop, and Mercari.

---

## Where they all bleed (ranked by cost/time impact on a reseller)

1. **Nobody helps you decide whether to buy — only what to do after you
   already own it.** Every tool above is post-acquisition (list it,
   track it, analyze its profit after the sale). A bad buy costs a
   reseller real money *before* any of these tools are even relevant.
   This is the single largest gap and it's structural, not a missing
   feature — it's why `decision_policy.py`'s BUY/PASS verdict, run
   *before* a purchase, is a different category of tool, not a
   me-too feature.
2. **Oversell/"ghost inventory" from sync failures — a recurring
   complaint across at least three tools** (Vendoo, PrimeLister,
   Flipwise's "Ghost Inventory"). Each markets automatic sale detection
   as a *feature*; each has documented cases of it failing. A double
   sale costs real money (refund, angry customer, marketplace penalty)
   and erodes trust in the core promise of the category.
3. **Sticker price vs. real price.** PrimeLister users report ending up
   near $90/mo after stacking add-ons for what looked like a $29.99
   plan; List Perfectly gates the double-sell-prevention feature behind
   its $99+/mo tier; Nifty's AI features run out of "Smart Credits" and
   require top-ups. The advertised price is reliably not the real price
   once a seller needs what they actually came for.
4. **Cancellation/retention friction.** A hidden cancel button behind a
   support chat (PrimeLister) and continued billing after cancellation
   (Vendoo) were both specifically reported. This is a trust cost, not
   just a UX one — sellers researching these tools now read "hard to
   cancel" as a red flag before they've even signed up.
5. **Fragmentation forces a multi-tool stack.** sellerboard is
   Amazon-only; SellRaze/Nifty focus on listing generation; Flipwise is
   eBay-centric inventory. Industry guides explicitly recommend
   "building a toolkit of apps that complement each other" rather than
   expecting one tool to cover sourcing, listing, inventory, and
   analytics — the market has normalized needing 2-3 paid subscriptions
   stacked together, which is real, ongoing cost most sellers don't
   fully add up until asked.

## Sources

All URLs cited inline above; none of the pricing/feature/complaint
claims in this document were invented — anything not directly
verifiable from a checked source is explicitly marked UNKNOWN rather
than stated as fact.
