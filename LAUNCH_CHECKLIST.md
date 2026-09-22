# Appraze™ Launch Checklist

Ordered, actionable, budget-conscious. Do the numbered sections in order —
later ones assume earlier ones are done. Costs are called out explicitly
so you know exactly where money is actually required vs. optional.
See `DEPLOY.md` for full secrets/setup detail this checklist points to.

## 0. Blocking issue found — fix this first (free)

**The production app currently looks private.** A direct check of
`https://appraze-ai-dkc8kpa7pbtzhgwpgztqyh.streamlit.app/` redirects to
Streamlit Community Cloud's own viewer-login gate, not straight to the
app. That's a separate, platform-level access gate on top of Appraze's
own login — if it's set to invite-only, nobody outside your invited
viewer list can reach the app at all, even to see the login screen.

Fix: on [share.streamlit.io](https://share.streamlit.io), open this app
→ **Settings** (⋮ menu) → the sharing/viewer-access section → set it to
whatever your intended public setting is called in the current UI
(historically labeled "This app is public" / viewer access). If you
*want* it private during a soft launch, that's fine too — just confirm
it's intentional, since right now it's ambiguous whether it was set that
way on purpose.

## 1. Legal pages (free, done this session)

`pages/9_📜_Legal.py` now ships Terms of Service, Privacy Policy, and
Refund Policy tabs, live automatically the next time you deploy. **Before
relying on them:**
- Replace every `[bracketed placeholder]` (support email, your
  state/country for governing law, refund request window) with real
  values.
- Have a lawyer glance at them before you lean on them in an actual
  dispute — they're accurate about what the app does, but they're not a
  substitute for legal advice, especially once real customer payments
  are flowing through it.

## 2. Stripe going live (Stripe itself is free until you take a payment — ~2.9% + 30¢ per transaction, no monthly fee)

Two separate things use Stripe here — know which one you're actually
launching:

- **Point-of-Sale ("Charge Customer" tab)** — fully wired and working
  today (creates a real Stripe Checkout Session per sale, no card data
  touches Appraze). This is what needs to go live for you to charge your
  own resale customers.
- **Subscription Pricing page** (`pages/8_💳_Pricing.py`) — **now has
  real Subscribe buttons** (added 2026-09-21), one per paid plan, each
  driven by its own Stripe Payment Link — see DEPLOY.md's "Card
  payments" section for exact setup steps and the new
  `STRIPE_PAYMENT_LINK_<PLAN>` secrets it needs. A plan with no secret
  configured shows a disabled "Not yet available" button instead of a
  broken link, so you can launch with just Appraiser (the flagship) live
  and add the rest later.

  **Important gap found while wiring this up:** the login gate every
  page actually uses (`auth.require_auth()`) only supports the one
  shared Admin account (you + Ashley) — there is currently no way for a
  member of the public to create their own account at all. The
  tester-signup code path (`auth.signup()` / `render_login_gate()`)
  exists and is fully wired to the Apps Script backend, but nothing
  calls it. **In practice, today, the only account that can click
  Subscribe is the shared Admin account** — which already has full
  access and nothing to gain from subscribing. If the plan is to sell
  Appraze to other resellers as a SaaS product (which the whole Pricing
  page and the public landing page imply), wiring public signup into the
  real entry point is the next concrete step, and it's a meaningful
  scope of its own (deciding what a new signup's workspace/data
  isolation looks like, whether "Free" accounts need any limits actually
  enforced, etc.) — worth its own session rather than folding into this
  one. Until then, treat the Pricing page as ready-to-demo and
  ready-for-the-admin-account-to-test, not yet ready for a stranger to
  actually use end-to-end.
- Also not yet built: nothing in the app currently checks a user's plan
  to gate a feature (`subscription_plans.feature_enabled()` exists and
  is unit-tested, but nothing calls it). Buying Appraiser today records
  "appraiser" as your plan; it doesn't unlock anything extra yet.
- Pricing tiers were renamed/restructured 2026-09-21 based on
  `COMPETITIVE-GAPS.md`'s research — "Hunter" is retired (renamed
  "Appraiser"), and a new "Analyst" tier ($35/mo) sits between Scout and
  Appraiser. See `subscription_plans.py`'s module docstring for the
  reasoning.

Steps to take Stripe live (POS and/or subscriptions):
1. In your Stripe Dashboard, toggle out of test mode (or use a separate
   live-mode API key set if you're keeping test mode for future dev).
2. Streamlit app secrets (⋮ → Settings → Secrets): change
   `STRIPE_SECRET_KEY` from `sk_test_...` to `sk_live_...`, and set
   `APP_URL` to the real production URL.
3. For subscriptions: create each plan's Payment Link and set its
   `STRIPE_PAYMENT_LINK_<PLAN>` secret — see DEPLOY.md.
4. **Re-deploy `AppsScript_Code.gs`** (paste the current version into
   your Apps Script project, Deploy → Manage deployments → new version)
   so it can store which plan a user is on — the old deployed version
   doesn't have this yet. This can't be verified from this environment;
   test it yourself with a real Stripe test-mode Payment Link before
   trusting it with real money.
5. (Recommended, optional) Deploy `stripe_webhook_server.py` so POS
   payments made on a customer's own device reconcile automatically
   instead of needing a manual "Check Status" click — see `DEPLOY.md`'s
   "Automatic payment reconciliation" section for the exact steps.
   **Free hosting option:** Render's free web-service tier or Fly.io's
   free allowance both work; the free tiers sleep after inactivity, so
   the first webhook after a quiet period can be slow (10-30s) —
   acceptable for a solo/beta operation, not for high volume.
6. Test with one small real charge to yourself before taking a real
   customer's card or advertising a subscription publicly.

## 3. Marketing / launch link (free)

A shareable landing page was published separately via Claude Artifacts —
see the link in this conversation. It's a public-by-default-private page
you can share whenever you're ready; it points at the production URL
above. Update it once the app's public/private setting from step 0 is
confirmed.

## 4. Custom domain (optional, ~$10-15/yr)

Streamlit Community Cloud's free tier does **not** support a custom
domain (e.g. `app.appraze.com`) — that needs a paid Streamlit plan or a
different host entirely. Skip this for launch; the `.streamlit.app` URL
is fine to start. Revisit only once there's revenue to justify it.

## 5. Mobile — start here, but know the real costs before spending anything

| Platform | Can build without paying anything? | Unavoidable cost | Blocked on |
|---|---|---|---|
| Android | Yes — debug APK via the repo's GitHub Actions workflow | $25 one-time (Google Play Console) — only needed for the *signed* Play Store release | **Currently broken — see below** |
| Windows | Yes — try PWABuilder.com first (see `windows/CRTC_WINDOWS_STORE_PLAN.md`) | One-time individual Partner Center fee (check current price) | Nothing blocking today |
| iOS | No | $99/year (Apple Developer Program) | **A Mac running Xcode — no way around this** |

### Android — fix this before anything else on mobile

The repo's `.github/workflows/android-twa.yml` CI pipeline has **failed
on all of its last several runs**, including today's, every time with
**zero jobs started** (not a code/build error — the job never begins).
That signature almost always means one of:
- GitHub Actions spending limit reached or billing not set up for this
  account (Settings → Billing and plans → Plans and usage, or "Spending
  limits") — most likely cause if this is a private repo, since private
  repos only get a limited free monthly Actions-minutes allowance.
- Actions disabled for the repo (Settings → Actions → General → "Allow
  all actions").

Check those two settings first — I can't see your GitHub billing state
from here. Once fixed, re-run it from the **Actions** tab →
`android-twa.yml` → **Run workflow**, then download the debug APK
artifact and sideload it onto a phone as a sanity check before spending
the $25 on a Play Console account.

For the actual signed Play Store release once the CI is healthy again:
1. Generate a release keystore (`keytool -genkeypair -v -keystore
   release.keystore -alias appraze -keyalg RSA -keysize 2048 -validity
   10000` — pick your own alias/passwords, store them somewhere safe,
   losing this keystore later means you can never update the app again
   under the same listing).
2. Add four GitHub repo secrets: `RELEASE_STORE_FILE_B64` (the keystore
   file, base64-encoded), `RELEASE_STORE_PASSWORD`, `RELEASE_KEY_ALIAS`,
   `RELEASE_KEY_PASSWORD`.
3. Re-run the workflow — it now also produces a signed release AAB.
4. Publish `https://<production-host>/.well-known/assetlinks.json` (see
   `android/assetlinks.example.json`) with the real SHA-256 fingerprint
   of that release certificate.
5. Create a Google Play Console account ($25 one-time), create the store
   listing (uses the same legal pages from step 1 for the required
   privacy-policy URL), upload the AAB, submit for review.

### Windows and iOS

See the updated plans in `windows/CRTC_WINDOWS_STORE_PLAN.md` and
`ios/CRTC_IOS_STORE_PLAN.md` — both now lead with the cheapest realistic
path and flag exactly what's blocking each one.

## Cost summary for "keep it cheap" planning

**$0 today:** web app hosting (Streamlit Community Cloud), legal pages,
this checklist, the marketing landing page, Stripe itself (until a
transaction happens), Android debug APK (once CI billing is fixed),
Windows PWABuilder attempt.

**Real money, only when you're ready:**
- Stripe's per-transaction fee (~2.9% + 30¢) — happens automatically,
  not a separate bill.
- Google Play Console — $25 one-time.
- Microsoft Partner Center — one-time individual fee (check current
  price).
- Apple Developer Program — $99/year, plus you need a Mac.
- A custom domain, if you want one later — ~$10-15/yr.
- Any paid API usage (Anthropic, eBay) scales with actual use — nothing
  is pre-committed; both fail safe to "not configured" if you leave a
  key blank.

Nothing above requires canceling anything to afford — the mobile-store
fees are the only unavoidable real costs, and none of them are needed
just to have the web app live and taking payments.
