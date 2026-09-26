# Beta → Paid Conversion Plan — Appraze

Goal: turn the 10 free beta testers into the first paying users on Oct 1.
Target: 5 of 10 convert (50%). Anything above that is gravy.

> **Engineering status check (2026-09-22, cross-checked against actual
> source this session — see `.agent/HANDOFF.md` for full detail):**
> - "Beta accounts can't pass the AI paid-user gate" — **not a blocker**.
>   `app.py`'s `BETA_AI_ACCESS = True` flag already lets any logged-in
>   account use AI during the free beta, bypassing the paid check
>   entirely. Flip it to `False` when paid gating should start (Oct 1).
> - "Stripe not wired" — **code is now wired** (this session): a real
>   Subscribe button + payment verification + account upgrade flow exists
>   end-to-end in `pages/8_Pricing.py`. What's still unverified: whether
>   `STRIPE_PAYMENT_LINK_URL`/`STRIPE_SECRET_KEY`/`STRIPE_WEBHOOK_SECRET`
>   are actually set in the **live** deployment's secrets (not just
>   possible locally) — that's a deployment-config check, not a code gap.
>   Nobody has run an actual payment through it yet — do that dry run
>   before Sep 29 per this plan's own "Signup/payment flow untested
>   end-to-end" item.
> - "Backend not deployed / OAuth still blocked" — **status unknown to
>   me, flagged for the owner**. If this refers to the same Google Apps
>   Script backend Appraze's core login/storage already depends on
>   (`AppsScript_Code.gs`), this is the single biggest risk to this whole
>   plan: no backend means no login, no storage, no AI quota enforcement
>   — nothing works. I have no visibility into Google Cloud Console's
>   OAuth consent screen review status; only the account owner can check
>   or resolve it.

## The offer (proposal — confirm before promising it)

**Founding Member deal, beta testers only:**
- Locked-in founding rate forever (proposed: $19/mo locked vs $29/mo public).
- "Founding Member" badge in the app.
- Direct line to you for feature requests during year one.

Why it works: they got in free, they know the price goes up Oct 1, and the
locked rate rewards them for being first. Scarcity is real — only 10 people
on earth get this deal.

## Proposed pricing (confirm — nothing below is final)

- Public launch price: $29/mo (or $290/yr).
- Founding Member (beta testers only): $19/mo locked for life.
- These numbers line up with your math: ~$25–50/mo per user toward the
  $100k/mo climb. Final call is yours.

### Market check (Sep 2026) — prices validated

Reseller SaaS clusters hard around three bands:
- Entry ($15–30/mo): Vendoo Starter $14.99, Crosslist Bronze $23.99,
  SellRaze Plus $23.99, PrimeLister Basic $29.99, List Perfectly Simple $29,
  Vendoo Growth $29.99.
- Mid ($35–60/mo): Crosslist Silver/Gold $35–40, Vendoo Pro $59.99,
  List Perfectly Business $49, PrimeLister Pro $49.99, SellRaze Pro $47.99.
- Pro ($70+/mo): List Perfectly Pro $69 → Pro Plus $99–249,
  SellRaze Elite $103.99.

$29/mo public sits exactly on the market's anchor price — it's where Vendoo
Growth, List Perfectly Simple, and PrimeLister Basic all sit. Not suspiciously
cheap, not premium without proof. $19/mo founding is a genuine ~35% lifetime
discount: meaningful, standard playbook, doesn't torch unit economics.
$290/yr = ~2 months free, which matches the market norm (Vendoo yearly = 2
months free; Crosslist annual = 30% off).

Honest flag: at $29 you're priced alongside tools that crosslist to 10+
marketplaces, which Appraze doesn't do yet. Your justification is the verdict
engine — deal math and buyer-premium auction math nobody else has. If that's
sharp on Oct 1, the price holds. If it's wobbly, $29 feels expensive next to
Vendoo Growth.

> **Cross-list reality check (added 2026-09-22, updated same day — eBay
> publishing now built):** the tools above (Vendoo, List Perfectly,
> Crosslist, PrimeLister, SellRaze) crosslist to 10+ marketplaces largely
> because most of those marketplaces (Mercari, Poshmark, Depop, Facebook
> Marketplace) have **no public API for third-party listing tools** —
> those tools almost certainly automate the marketplace's own web form
> (browser automation / session replay), which is exactly what CRTC's own
> stated rules forbid. Those marketplaces remain draft-only in Appraze by
> design, not oversight.
>
> **eBay is done:** `ebay_listing.py` + `pages/5_Cross_List.py` now do
> real eBay listing creation (Sell Inventory API, Authorization Code
> OAuth — a seller connects their own eBay account once, then publishing
> a READY_TO_PUBLISH draft creates an actual live eBay listing). Built
> and unit-tested (25 tests, all mocked network) this session — **not yet
> exercised against a real eBay account**, because that needs three
> things only the account owner can do:
> 1. Register a redirect ("RuName") in the eBay Developer Portal for this
>    app's OAuth callback.
> 2. Set up at least one payment/return/fulfillment business policy in
>    Seller Hub — every offer references one, and the app has no way to
>    create or guess these.
> 3. Confirm the developer account's Sell APIs are enabled for whichever
>    environment you test in (sandbox is usually available by default;
>    production Sell API access can need eBay's own review, similar to
>    Stripe Connect going live).
>
> Once those three are done and `EBAY_CLIENT_ID`/`EBAY_CLIENT_SECRET`/
> `EBAY_RUNAME` are set in Streamlit secrets, do a real sandbox test
> before trusting it with a live listing — same "verify before you trust
> it" rule as the Stripe flow above.

Recommendation: launch with the single $29 tier + $19 founding lock. Add
volume/feature tiers later once usage data shows you the segments. Keep the
founding lock lifetime — with only 10 people it costs almost nothing and buys
you evangelists plus real urgency.

## Timeline

**Mon Sep 22 — Beta opens**
- 10 spots fill. Welcome email goes out: what to do first (run 3 deals through
  the deal math), where to report bugs, and one line: "Free through Sep 30.
  Founding Member rate if you stay."
- Plant the seed early. No hard sell on day one.

**Fri Sep 25 — Mid-beta check-in**
- Personal message to each tester: "What have you run through it? What's broken?"
- Fix fast, in public (changelog or group message). Nothing converts like
  "I asked, he shipped it in 48 hours."
- Ask for one screenshot or one-liner about a deal it helped with. This is your
  launch-day social proof.

**Sun Sep 28 — 72-hour warning**
- Email + in-app: "Beta ends Sep 30. Founding Member rate ($19/mo locked)
  expires with it. After Oct 1 it's $29 and the founding deal is gone forever."
- Include 2–3 tester quotes/screenshots from the Sep 25 check-in.

**Wed Oct 1 — Paid launch day**
- Morning: "Doors open" message. Payment link live.
- Evening: personal nudge to anyone who hasn't converted. One message, not three.
- Anyone who doesn't convert loses access Oct 2 by default — the default
  matters, because it's what creates urgency. But extensions are earned, not
  given (see below). Free extensions for everyone train people to wait.

## Extensions: earned, not given

Chris's call: whether a non-payer gets extra time depends on their potential
future value — their business, their volume, how real they are. Framework:

**Grant a short extension (7 days max) when:**
- They actually ran deals through the app in beta (activated, not curious).
- They're a working reseller with real volume — future $29/mo × 12 is worth
  a week of patience.
- They give a concrete reason (travel, card issue, family emergency).

**Never extend when:**
- They never logged a deal in beta.
- They won't put a card on file.
- The reason is vague ("I'll pay soon," "just need more time").

**How to frame it:** "I'll give you 7 days, card on file, it bills automatically
on day 8 unless you cancel." The extension becomes a trial-to-paid bridge, not
a freebie. One extension per person, no seconds.

## Conversion mechanics

1. **Card on file before Sep 30.** Don't wait until Oct 1 to discover someone's
   card fails. Collect payment details during beta (Stripe, free until Oct 1).
   Anyone who won't put a card down by Sep 28 is a no — stop chasing them.
2. **Make the first win fast.** Beta testers who run one real deal through the
   app in the first 48 hours convert. Testers who never log a deal don't.
   Your Sep 23 job: get all 10 to run deal #1.
3. **One ask per touchpoint.** Welcome = run a deal. Sep 25 = feedback.
   Sep 28 = lock your rate. Oct 1 = pay. Never stack asks.
4. **Testimonials are the launch fuel.** Every quote and screenshot from beta
   goes on the launch page and launch posts.

## What to track

- Beta activation: how many of the 10 run ≥1 deal in week one (target: 10/10)
- Card-on-file rate by Sep 28 (target: 8/10)
- Conversion rate Oct 1–2 (target: 5/10)
- Reason for every "no" — log it, it's your objection list for the public launch

## Blockers that kill this plan

Be straight about these — if any are red on Oct 1, conversion goes to zero:
- Backend not deployed / OAuth still blocked → no working app, no sale.
- Stripe not wired → can't take money.
- Beta accounts can't pass the AI paid-user gate → testers hit a wall.
- Signup/payment flow untested end-to-end → do a full dry run Sep 29 with
  a real card (yours), refund it after.

## After Oct 1

- Converted founders become your street team: referral perk (one free month
  per paying referral is the standard move — your call).
- The 5 who didn't convert go on a waitlist, not a guilt list. Invite them
  back at public price when v2 lands.
- Next milestone: first $1k MRR. That's ~35–50 paying users at these prices.
  That's when the growth-engine question gets urgent.
