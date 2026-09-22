# Appraze Master Backlog

Chris's ideas live here so nothing gets dropped. Claude maintains this
file: new ideas go under the right section, shipped items move to
Shipped with the date. Never delete shipped items.

## Now (beta → paid launch)
- [ ] Public signup wiring — strangers can't sign up or pay yet; only the shared Admin account works (BLOCKER for SaaS)
- [ ] Full test suite green, live beta URL — tests are green (381 passed as of 2026-09-21 night); **live beta URL is still blocked** — tonight's work is on a feature branch, not `main`, and Streamlit Cloud auto-deploys from `main` only. Needs a merge decision before "ships tomorrow" is actually true. See LAUNCH_CHECKLIST.md / .agent/HANDOFF.md.
- [ ] Stripe: checkout idempotency (shipped — see Shipped below), webhook reconciliation-failure HTTP status — currently returns 2xx even when internal reconciliation/persistence fails (intentional, avoids Stripe retry storms, but conflicts with this backlog item's literal ask of "non-2xx on failure"). Flagged, not silently resolved either way — needs a decision, not a guess.
- [ ] Auth hardening: brute-force protection, bcrypt/Argon2 (no unsalted SHA-256) — in progress tonight, see auth.py
- [ ] Real feature gating/paywall or hide Pricing — Pricing page has real Subscribe buttons (wired 2026-09-21 earlier today, before tonight's "don't build billing tonight" instruction arrived). Currently fails safe: buttons only go live if real Stripe Payment Link secrets are manually configured, which won't happen by accident during a free beta. Left as-is rather than reflexively ripped out — flag if you want it explicitly hidden/disabled for the free-beta window instead.
- [ ] Visitor/engagement analytics — "how many people visit and how long they stay" (owner request, 2026-09-21). Not built tonight (sprint rule: no new features tonight). Simplest real options for later: Cloudflare Web Analytics or Plausible for the public landing page (free/near-free, privacy-friendly, one script tag, no cookie banner needed); in-app usage should route through the beta-telemetry direction already documented in CRTC_HANDOFF.md ("2026-09-20 — Beta telemetry / product learning direction") rather than a third-party script inside an authenticated app.

## Next (Appraze differentiators — the math moat)
- [ ] Pallet / bulk-lot manifest analyzer (CSV upload → comps → fees/condition adjustment → max bid)
- [ ] Fee-aware cross-list repricer (automatic +8–15% secondary-platform fee offset)
- [ ] Buyer-premium all-in max-bid calculator (freemium wedge)
- [ ] eBay official Sell API publishing first, then Etsy; assisted "we open the tab, you click publish" flow + delist tracker for Poshmark/Mercari/Depop/FB Marketplace (no public APIs there)

## Later (new flagship lane — separate brand, NOT Appraze)
- [ ] Estate-sale company software at $49–149/mo/seat: sale setup, fast photo intake, checkout-line POS, pickup windows, settlement + commission tracking (~35% avg), unsold disposition
- [ ] VALIDATE FIRST with the Charleston outreach list before writing any code

## Platform expansion (Chris's order)
- [ ] Android (Google Play) → Windows → iOS

## AI employees (only after paid launch + real users + real support load)
- [ ] AI support agent: customer complaints, order updates, FAQs
- [ ] No premature automation — support load comes first

## Shipped
- **2026-09-21** — Appraze rebrand applied everywhere (no leftover CRTC/BUSINESS OS as a product name) — swept and reconfirmed clean multiple times today, most recently right before tonight's sprint began.
- **2026-09-20** — Decision-engine canonical-engine fixes: buyer-premium parsing goes through `number_normalize.parse_percent_points` (kills the 0.18-vs-18% unit bug), `decision_policy.evaluate_deal()` is the one canonical BUY authority both auction and non-auction paths route through, dashboard/pipeline verdict divergence eliminated — pre-dates tonight, confirmed still holding during tonight's audit (see DEAL-MATH.md).
- **2026-09-21 (tonight)** — Decision-engine audit: sourced 2026 fee/premium/tax research, fixed a real fee-basis bug in `flip_ledger.calculate_flip_profit` (buyer-paid shipping wasn't in the fee basis, overstating profit), added purchase-side sales tax as an explicit tracked cost component in `decision_policy.py`, added sourced per-platform fee guidance to the Profit Calculator/Inventory sliders. Full writeup in DEAL-MATH.md.
