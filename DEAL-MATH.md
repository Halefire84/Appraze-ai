# Appraze — Deal Math Specification

_Written 2026-09-21 as part of the pre-beta decision-engine audit. This
is the canonical explanation of every money formula in Appraze: what it
computes, why, where the real-world numbers came from, and what's
explicitly still an assumption. If a formula in the code can't be
explained by something in this document, that's a bug — flag it._

If you're the next person (human or agent) touching money math in this
repo: read this file, then read `decision_policy.py`'s own docstring
(it documents the same invariants from the code side). Don't duplicate
a formula that already exists in `finance.py` or `decision_policy.py`.

## Contents
1. Real-world fee/premium/tax data (sourced)
2. The canonical formulas, one by one
3. Worked examples
4. Explicit assumptions and known simplifications
5. UNKNOWN — needs a human decision

---

## 1. Real-world data (researched 2026-09-21, every number sourced)

### Marketplace resale fees

| Platform | Fee | Basis | Source |
|---|---|---|---|
| eBay | ~13.6% (standard categories) + $0.30/$0.40 per order | Item price + handling + **buyer-paid shipping** + tax + other applicable amounts | [eBay Seller Center](https://www.ebay.com/sellercenter/selling/start-selling-on-ebay/seller-fees), [Taxomate 2026 breakdown](https://taxomate.com/blog/ebay-seller-fees) |
| eBay — clothing/media | ~15.3% | Same basis as above | [Underpriced AI eBay fee guide](https://www.underpriced.app/blog/ebay-fees-complete-guide-2026) |
| eBay — jewelry & watches | ~15% (tiered) | Same basis | same |
| eBay — athletic shoes >$150 | 8%, no per-order fee | Same basis | same |
| eBay — guitars & basses | 6.7% | Same basis | same |
| Poshmark | 20% of sale, or flat $2.95 under $15 | Sale price (Poshmark's 20% is described as including built-in shipping cost) | [Voolist Poshmark 2026](https://www.voolist.com/blog/poshmark-fees-2026) |
| Mercari | 10% flat, no separate processing fee | Item price **+ buyer-paid shipping** | [Vendoo marketplace fee guide](https://blog.vendoo.co/a-resellers-guide-to-marketplace-fees) |
| Etsy | 6.5% transaction fee + 3%+$0.25 payment processing + $0.20 per listing | Sale price (listing fee is per-item, charged regardless of sale) | [Voolist marketplace comparison 2026](https://www.voolist.com/blog/marketplace-fees-comparison-2026) |
| Depop (US) | ~3.3% + $0.45 payment processing, no separate commission | Sale price | [Voolist Poshmark/Mercari/Depop comparison](https://www.voolist.com/blog/poshmark-vs-mercari-vs-depop) |

**What this means for Appraze:** a single flat "resale fee %" (the
app's current 13% default) is a blend, not any one platform's real
number — the real spread is 3.3% to 20%, a 6x range. This is now
surfaced as slider help text in the Profit Calculator and Inventory
tabs (fixed 2026-09-21) rather than a silent, unlabeled default. A full
per-platform auto-selected fee table is a larger, this-week-or-later
change (see "UNKNOWN" below) — tonight's fix is making sure the user
knows what number to type in, not auto-selecting it for them yet.

### Auction buyer's premium

- **CTBids: 18% flat**, confirmed directly — matches `finance.py`'s
  `DEFAULT_PREMIUM_PCT = 18.0` exactly. [Multiple CTBids estate-sale
  listings](https://ctbids.com/) display this rate; no contradicting
  source found. **Verified clean, no change needed.**
- Fine-art/collectibles auctions commonly use **tiered/sliding-scale**
  premiums (e.g. a higher % on the first portion of the hammer price,
  lower above a threshold) — [Grossman LLP on 2026 buyer's-premium
  changes](https://www.grossmanllp.com/strongspring-2026-auction-season-examining-recent-changes-in-buyers-premiumsstrong),
  [Buyer's premium — Wikipedia](https://en.wikipedia.org/wiki/Buyer%27s_premium).
  Appraze's flat-percentage model does **not** capture tiered premiums.
  For Appraze's actual target market (household goods, jewelry, estate
  items — not fine art), a flat rate is a reasonable simplification,
  but don't assume it holds for a high-value fine-art lot at an
  unfamiliar house. Flagged in the Profit Calculator's slider help text.
- No CTBids-specific tiering was found in the sources checked — treat
  CTBids as flat 18% unless a specific listing says otherwise.

### Sales tax — marketplace facilitator laws

- eBay, Etsy, Poshmark, and Mercari are all **marketplace facilitators**
  under state law and **collect and remit sales tax on the sale side
  automatically** — the seller does not calculate or collect it.
  [Synder 2026 marketplace facilitator
  guide](https://synder.com/blog/marketplace-facilitator/), [eBay/Etsy
  specifics](https://milesconsultinggroup.com/2026/06/who-collects-and-remits-sales-tax-when-you-sell-through-a-marketplace-platform/).
- This means `finance.sales_tax()` — used only for the POS/in-person
  checkout flow — is **correctly scoped already**. Online marketplace
  sales don't need Appraze to compute sale-side tax; in-person sales
  (not facilitated by a marketplace) do, and that's the only place it's
  used. **Verified clean, no change needed — don't "fix" this into
  computing tax on marketplace sales, that would double-collect.**
- **Purchase-side tax is different and was a real gap** (fixed
  2026-09-21, see below): many auction houses charge sales tax on the
  hammer price + premium **unless the buyer has a resale exemption
  certificate on file.** Whether that applies is business-specific — see
  "UNKNOWN" below.

### Shipping — dimensional weight (informational; not currently automated)

- As of 2026, USPS, UPS, and FedEx domestic parcel rates all use a
  **dimensional weight divisor of 139** (USPS changed from 166 to 139 in
  July 2026, converging with UPS/FedEx): `(L × W × H, each rounded up to
  the next whole inch) ÷ 139`, rounded up to the next pound; the higher
  of dimensional weight or actual weight is billed. Packages ≤1,728
  cubic inches (1 cubic foot) are always billed by actual weight. [DCL
  Logistics 2026 USPS DIM change](https://dclcorp.com/blog/shipping/usps-dim-weight-changes-2026/),
  [Scale Blog divisor
  139](https://scaleblog.com/what-is-dimensional-weight-shipping/).
- Appraze doesn't calculate shipping automatically anywhere today —
  `shipping` is always a plain user-entered dollar amount. This isn't a
  bug (the app never claims to estimate it), just useful reference data
  if a shipping-cost estimator is ever built.

### The 70% acquisition rule — honest origin

`decision_policy.py`'s `ACQUISITION_TARGET_PCT = 70.0` ("the classic
CRTC 70% rule") is **borrowed from real-estate house-flipping**, not a
native reselling-industry standard — the "70% of ARV minus repairs"
rule is a well-established quick-screening heuristic for property
flippers. [FlipperForce 70%
rule](https://flipperforce.com/70-percent-rule-formula), [BiggerPockets
discussion](https://www.biggerpockets.com/forums/12/topics/1007633-using-the-70-rule-on-fix-flip).
The logic translates reasonably to resale goods (the 30% held back
covers fees/shipping/time-value/profit instead of repairs/holding
costs), but it is an **adapted heuristic, not an eBay/resale-industry
benchmark** — the in-code comment calling it "the classic CRTC rule"
shouldn't be read as implying outside authority it doesn't have. No
code change; this section exists so nobody "fixes" the comment into
overclaiming.

---

## 2. The canonical formulas

**One canonical engine.** Every deal decision in the app is supposed to
route through `decision_policy.evaluate_deal()`, which itself calls
`finance.calc_deal()` for the core profit/ROI math. Don't add a new
BUY-producing formula anywhere else — extend `evaluate_deal()`.

### `finance.calc_deal(cost, resale_value, fee_pct, premium_pct)`

```
true_cost   = cost × (1 + premium_pct / 100)
net_resale  = resale_value × (1 - fee_pct / 100)
gross_profit = net_resale - true_cost
roi_pct     = gross_profit / true_cost × 100   (or +∞ for a $0-cost profitable find)
```

Verdict tiers (`finance.five_tier_verdict`): STRONG BUY ≥60%, BUY ≥40%,
AT CEILING ≥20%, BORDERLINE ≥5%, PASS <5%.

### `decision_policy.evaluate_deal(...)` — the canonical decision

Adds, on top of `calc_deal`:
- **Acquisition-ceiling check**: `target_all_in = market_value × 0.70`
  (see the 70%-rule note above). BUY requires the all-in cost (price +
  known premium + known shipping + known other_fees + known
  purchase_tax) to fall at or under that ceiling.
- **Explicit cost states** per component: `KNOWN | UNKNOWN | ESTIMATED |
  NOT_APPLICABLE`. An `UNKNOWN` *material* cost (buyer's premium on an
  auction, or shipping when required) blocks a hard BUY — the decision
  becomes `REVIEW` or `CONDITIONAL BUY` with the missing item named, never
  a silent $0.
- **Dual-scale disclosure**: the acquisition rule (70% of value) and the
  finance ROI tier can disagree — a deal right at the 70% ceiling
  typically nets ~24% ROI after a 13% resale fee, which is `AT CEILING`
  on the ROI scale even though it's `BUY` on the acquisition scale.
  Both are always surfaced together, never just one.
- **Purchase-side tax** (added 2026-09-21): `purchase_tax`, an optional
  named USD cost component, same KNOWN/NOT_APPLICABLE treatment as
  shipping/other_fees. Defaults to NOT_APPLICABLE (omitted) so every
  existing caller is unaffected.

### `flip_ledger.calculate_flip_profit(cost_basis, sale_price, fee_pct, shipping_out, shipping_charged)` — realized profit after a sale

```
fee_basis    = sale_price + shipping_charged     (fixed 2026-09-21 — was sale_price alone)
platform_fee = fee_basis × fee_pct / 100
net_proceeds = sale_price + shipping_charged - platform_fee - shipping_out
profit       = net_proceeds - cost_basis
margin_pct   = profit / sale_price × 100
roi_pct      = profit / cost_basis × 100   (or +∞ for a $0-cost profitable find)
```

### `auction_costs.calculate_auction_cost(bid, buyer_premium_pct, shipping, other_fees)` — pre-purchase acquisition cost

```
premium_amount = bid × buyer_premium_pct / 100
all_in_cost    = bid + premium_amount + shipping + other_fees
```
Routes `buyer_premium_pct` through `number_normalize.parse_percent_points`
so "18", "18%", and the 0.18-fraction ambiguity all resolve to the same
18 percentage points — this is the fix for the historical "0.18 read as
0.18%, a 100x unit error" bug class.

### `acquisition_hunter.estimate_max_bid(listing, target_margin=0.30)` — liquidation/bulk-lot ceiling

```
effective_resale       = expected_resale × recovery_rate
max_total_acquisition  = effective_resale × (1 - target_margin) - fixed_costs
```
where `fixed_costs` sums `buyer_premium + tax + freight + repair_cost +
accessory_cost + other_costs` — **note:** in this module, `buyer_premium`
is a **dollar amount**, not a percentage, unlike `auction_costs.py` and
`decision_policy.py` where the same field name means percentage points.
Each pipeline is internally self-consistent (this module's own UI in
`pages/2_📦_Liquidation_Surplus.py` collects it as a dollar amount), so
this is not an active bug today, but it's a real naming collision across
modules — see "UNKNOWN / this week" below.

---

## 3. Worked examples

**Standard BUY** (the app's own defaults: 13% resale fee, 18% buyer's
premium — matches `tests/test_smoke.py`'s `test_verdict_scale_buy`):
cost $100, resale $190 → true_cost $118.00, net_resale $165.30, profit
$47.30, ROI 40.08% → **BUY**.

**STRONG BUY**: cost $100, resale $400, same fees/premium → true_cost
$118.00, net_resale $348.00, profit $230.00, ROI 194.9% → **STRONG BUY**.

**PASS**: cost $100, resale $104, same fees/premium → ROI ≈ 2% →
**PASS**.

**Fee-basis fix, before/after** (the flip_ledger bug fixed tonight):
cost basis $100, sale $250, fee 13%, shipping out $15, shipping charged
to buyer $10.
- **Before (wrong):** fee = $250 × 13% = $32.50 → profit $112.50.
- **After (correct):** fee = ($250+$10) × 13% = $33.80 → profit $111.20.
- Difference: $1.30 overstated profit on this one sale — small in
  isolation, systematic across every sale with buyer-paid shipping.

**Purchase tax, before/after** (the decision_policy.py addition
tonight): auction bid $100, 18% premium, $10 shipping, market value
$200, no tax vs. $9 tax.
- Without tax: all-in cost $128.00.
- With $9 purchase tax: all-in cost $137.00, and projected ROI drops
  accordingly — see `tests/test_decision_engine_audit_2026_09_21.py`
  for the exact assertions.

---

## 4. Explicit assumptions and known simplifications

- Resale fee is a single user-adjustable percentage, not an automatic
  per-platform/per-category lookup (see the fee table above — now
  surfaced as slider help text, not auto-selected).
- No fixed per-order fee (eBay's $0.30/$0.40) is modeled anywhere.
  Small in dollar terms for typical resale item values; not yet added.
- Auction buyer's premium is modeled as flat-percentage only — tiered/
  sliding-scale premiums (common at higher-value art/collectibles
  auctions) are not represented.
- Shipping is always user-entered; no dimensional-weight estimator
  exists yet (reference formula above if one gets built).
- Money math throughout uses Python floats, not `Decimal`/cents. This
  is a known, deliberate deferral — the full canonical-module/Decimal
  rewrite is this week's work, not tonight's, per the sprint plan. Two
  real float-related issues (the flip_ledger `roi_pct` rounding gap, and
  the general float-precision class this rewrite is meant to close) are
  documented here rather than silently left for someone to rediscover.

## 5. UNKNOWN — needs a human (Chris) to decide

- **Full eBay category-by-category fee table.** Sourced numbers above
  cover standard/clothing/media/jewelry/shoes/guitars, not eBay's entire
  category list (hundreds of categories, from [eBay's official fee
  table](https://www.ebay.com/sellercenter/selling/start-selling-on-ebay/seller-fees)).
  Building a full automated per-category lookup is a real feature
  decision, not something to guess at.
- **Whether/how to auto-select resale fee % by platform.** The Deal
  Dashboard already has a `Platform` field per deal — wiring it to
  suggest (not silently override) the matching fee % is a reasonable
  next step, but changes existing UI behavior and needs a product
  decision on whether the suggestion should be a default or just a
  hint.
- **Resale exemption certificate status.** Whether purchase-side sales
  tax actually applies depends on whether the business holds a resale
  certificate in the relevant state(s) — that's a real
  business/accounting fact only Chris (or an accountant) can supply, not
  something to assume either way. `purchase_tax` defaults to
  NOT_APPLICABLE; flip it to KNOWN with a real amount only when it's
  confirmed to apply.
- **`buyer_premium` naming collision** between `acquisition_hunter.py`
  (dollar amount) and `auction_costs.py`/`decision_policy.py`
  (percentage points). Not an active bug (each pipeline is internally
  consistent), but a real footgun for future development — matches the
  original master-direction ask to standardize buyer-premium units
  everywhere. Rename to `buyer_premium_amount` vs. `buyer_premium_pct`
  explicitly — this-week work, touches `acquisition_hunter.py` and the
  Liquidation Surplus page's UI, not done tonight to keep tonight's
  diff small right before a beta ship.
- **The canonical Decimal/cents rewrite, probabilistic verdicts with
  confidence intervals, and the fixed per-order-fee addition** are all
  explicitly this-week (or later) work per the sprint plan, not
  attempted tonight.
