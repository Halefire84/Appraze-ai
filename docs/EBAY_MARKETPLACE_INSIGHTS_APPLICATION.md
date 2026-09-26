# eBay Marketplace Insights API — application draft

Per `briefs/comps-collector-brief-2026-09-26.md`: this is a business-justification draft for
Chris to paste into eBay's own application form. **He submits it himself** — there is no
"apply via code" step, and eBay's own developer forum reports this approval now goes almost
exclusively to large/enterprise partners, so expect a "no" and don't block anything on it.

Where to apply: eBay Developers Program → Application Keys → the app's production keyset →
request access to **Buy APIs → Marketplace Insights**. The exact form fields change over
time; use the text below as source material, not a literal fill-in-the-blanks template.

---

**Application name:** Appraze (Cooper River Trading Co.)

**What does your application do?**

Appraze is a resale-business tool for individual and small-business resellers (estate sales,
auctions, thrift/Goodwill sourcing, general secondhand goods). Before buying an item, a
reseller enters what they'd pay for it; Appraze looks up comparable eBay listings and
computes an estimated resale value, profit, and ROI so the reseller can make an informed
buy/pass decision *before* spending money. This is the same "should I buy this to resell"
workflow every reseller already does manually by searching eBay — Appraze automates the
comps lookup and the profit math, it does not automate buying, selling, or listing without a
human decision at every step.

**Why do you need Marketplace Insights specifically (not just Browse)?**

We already use the Browse API for active/asking-price listings, and disclose plainly to our
users when a valuation is based on asking prices rather than actual sales (our own confidence
labeling downgrades asking-price-only estimates). Marketplace Insights' actual sold-price data
would let us give resellers a materially more accurate, evidence-based valuation instead of an
asking-price proxy — directly improving the quality of the buy/pass decisions we help people
make, and reducing the number of bad purchases made on a misleading asking-price signal.

**Expected call volume:**

[Chris: fill in your actual expected usage here honestly — e.g., "X comps lookups/day from
our current user base of Y active users, expected to grow to Z over the next N months."
Do not overstate volume to seem more enterprise-y than the app currently is; eBay can revoke
access for misrepresentation, and an honest small-scale number is a legitimate application,
not a weak one.]

**Data handling / compliance:**

Sold-price data is used only to compute an aggregate summary (median, count, a confidence
rating) displayed to the user who requested that specific lookup. We do not republish,
resell, or bulk-export eBay sold-listing data; no per-listing sold data is stored longer than
needed to compute that one summary [Chris: confirm this matches how you actually want to
operate it — comps_collector.py currently caches a rollup for 1 hour per query, not the raw
listing records long-term; state that accurately].

**Company / developer account standing:**

[Chris: list how long the eBay developer account has existed, whether it's in good standing,
any existing production API usage (Browse, Sell APIs if applicable) to show a track record.]

---

## If eBay says no (the likely outcome)

Nothing changes operationally — `comps_adapters.EbayMarketplaceInsightsAdapter` already
handles this gracefully (raises `EbayInsightsNotApprovedError`, both `comps_collector.py` and
`comps_poller.py` catch it and fall back to Browse API active listings automatically). This
application costs nothing to submit and costs nothing to have rejected.
