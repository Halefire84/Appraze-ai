# Appraze™ / CRTC — Agent Handoff

Read this first. It is meant to stand on its own, without conversation
history. For deep narrative detail on any item below, see
`CRTC_HANDOFF.md` (chronological session log, ~900 lines) and
`APPRAZE_BRAND.md` (brand record).

## What this product is

**Appraze™** ("Complete Resale Business Suite") — deal math, inventory,
and listing for resellers. Built by **Cooper River Trading Co. (CRTC)**,
which is now the company name only, never the product name. Single-page
Streamlit app (`app.py`) plus several `pages/*.py` tools (Opportunity
Radar, Auction Hunt, Liquidation Surplus, Holy Grail Finder, Government
Electronics, Deal Workspace, Flip Ledger, Cross-List, Pricing), a
standalone FastAPI Stripe-webhook service (`stripe_webhook_server.py`),
and Android/iOS/Windows wrapper scaffolding.

## Branding — settled 2026-09-21, logo done same day (see `APPRAZE_BRAND.md`)

Product name is **Appraze**, spelled A-p-p-r-a-z-e (not "appraise").
"BUSINESS OS" / "LLAVE" / "TURNKEY" are all retired working names from an
earlier multi-day rebrand saga — do not reintroduce them. `CRTC_NAME.md`
and `BUSINESS_OS_BRAND.md` are superseded history, not current direction.

The app also had many pages (Opportunity Radar, Auction Hunt,
Liquidation Surplus, Holy Grail Finder, Government Electronics, Deal
Workspace, Flip Ledger) still speaking as **"CRTC"** throughout their
body text/buttons/footers even after the rebrand — only page titles had
been fixed. Swept and fixed later the same day. If you find more stray
"CRTC" used as a product name (vs. the company) anywhere, fix it; the
company name is the only correct use of "CRTC" now.

**Logo:** an original SVG mark now exists — `static/appraze-mark.svg`
(rounded-square badge) and `static/appraze-mark-maskable.svg` (full-bleed,
Android-safe-zone-padded variant), a gauge/dial ring of tick marks around
a bold monoline "A". Wired into the sidebar/header (replacing a leftover
🔑 key emoji from the TURNKEY era), the PWA manifest icons
(`static/icon-192/512/512-maskable.png`, re-rendered from the SVGs — 
regenerate from source if the mark ever changes, don't hand-edit the
PNGs), and full platform icon sets for Android (`android/app/src/main/res/mipmap-*`,
wired into `AndroidManifest.xml`'s `android:icon`/`android:label`, which
previously had none), iOS (`ios/AppIcon/`, ready to drop into an
`AppIcon.appiconset` once a real Xcode project exists — none does yet),
and Windows (`windows/AppIcons/`, a fallback since the recommended
PWABuilder.com path generates its own). `APPRAZE_BRAND.md`'s
visual-direction section documents all of this.

Trademark marks, memorial dedication (comment header block in every
entry-point module + an "In Memory" / "For the Future" section with real
photos on a new About tab in `app.py`), and non-functional
build-provenance watermark constants (`_APPRAZE_BUILD_ATTRIBUTION`) in
`finance.py`/`storage.py`/`app.py` with a playful non-blocking tamper
banner were also added 2026-09-21. **Two hidden easter-egg dialogs (a
"christopher hale" and a "live long and prosper" search-box tribute)
were added, then removed the same day at the owner's request** — felt
"weird" for a memorial; the About tab's plain, always-visible section is
the one memorial now. Don't re-add the dialogs. None of this touched
financial/business logic. Full detail in `CRTC_HANDOFF.md` under
"2026-09-21 — Final rebrand to Appraze™..." and the entries after it.

## Canonical financial/decision engine — already built (2026-09-20)

The owner's "New Master Development Direction" (a simulation campaign
that found 4 High / 5 Medium / 7 Low / 1 Informational findings) asked
for one canonical BUY/decision authority and a shared financial
normalizer. **Both already exist:**

- `decision_policy.py` — the one source of truth for estimated resale
  value, acquisition cost, projected profit/ROI, max allowable
  acquisition price, confidence, and final recommendation. Documented
  policy: acquisition ceiling = 70% of market value (the classic CRTC
  rule); ROI tiers reported alongside every decision — STRONG BUY ≥60%,
  BUY ≥40%, AT CEILING ≥20%, BORDERLINE ≥5%, PASS <5%. Other modules
  (`deal_workspace.py`, `auction_radar.py`, `crtc_opportunity.py`,
  `pages/*`) are required to call `evaluate_deal()`/`build_decision()`
  rather than inventing their own thresholds — verify this invariant
  still holds before adding any new BUY-producing code path.
- `number_normalize.py` — the single parser for messy marketplace
  numbers/currency/percentages, distinguishing dollars vs. percentage
  points vs. fractional percentages vs. unknown.
- `tests/test_p0_regression.py` — a permanent regression suite keyed to
  the simulation's findings, named `test_f0N_...`. Currently covers
  **F01–F06, F08–F13** (canonical-engine disclosure, Stripe signature
  staleness/freshness, refund amount-vs-boolean correctness, category
  normalizer not self-validating, unknown-shipping not forcing a hard
  BUY, buyer-premium fraction normalization, distinct SKUs for manual
  flips, out-of-order webhook state precedence, invalid/NaN/Infinity
  costs never producing BUY, non-ASCII signature headers, secret-rotation
  signature acceptance). **F07 and F14–F17 have no test in this file** —
  check the simulation's original finding list (if you can find it — it
  wasn't preserved verbatim in this repo, only the F-numbers survived in
  `CRTC_HANDOFF.md`'s "P0 hardening" entry) and confirm whether F07/F14-17
  are genuinely closed, not applicable, or still open before claiming the
  full master-direction checklist is done.

**This session did not re-audit that engine.** It only confirmed
`python3 -m pytest -v` stays green (367 → 374 tests across today's
commits) before and after the branding/launch-prep changes. Do not
assume the full 20-item master-direction quality gate (security audit,
mobile/Windows/web production-readiness review, etc.) is complete just
because these tests pass — see "Still open" below.

## Subscription billing — wired 2026-09-21, has a real gap

`pages/8_💳_Pricing.py` now has working "Subscribe" buttons per paid
plan, driven by per-plan Stripe Payment Links
(`STRIPE_PAYMENT_LINK_<PLAN>` secrets — see `DEPLOY.md`). On return,
`app.py` verifies the Checkout Session actually paid, then calls
`auth.mark_paid(username, plan)`, which now also persists *which* plan
(a new trailing `plan` column on the Apps Script `Users` sheet,
migrated automatically — **but the deployed Apps Script must be
re-pasted/re-deployed from the current `AppsScript_Code.gs` first**, or
the old deployed version won't understand the new `plan` parameter at
all).

**The real gap: `auth.require_auth()` — the login gate every page
actually calls — only supports the single shared Admin account.** There
is no live way for a member of the public to sign up for their own
account today. `auth.signup()` / `render_login_gate()` (public
signup/tester login) exist, are unit-tested, and talk to the same Apps
Script backend, but nothing calls them from any page. So right now the
Pricing page's Subscribe buttons are reachable, and will correctly
record a plan against whoever's logged in — but that's only ever the
shared Admin account, which already has full access and nothing to
gain. If the intent is a real multi-tenant SaaS (which the Pricing
page, the public landing artifact, and `pages/9_📜_Legal.py`'s Terms of
Service all already assume), **wiring public signup into the real entry
point is the next concrete step** — and it's its own scope (workspace/
data isolation for a new signup, whether Free-tier limits are actually
enforced anywhere, etc.), not something to bolt on casually. See
`LAUNCH_CHECKLIST.md` section 2 for the full writeup.

Also still true: `subscription_plans.feature_enabled()` exists and is
unit-tested, but nothing in the app calls it — buying a plan today
records the purchase but doesn't unlock or restrict anything yet.

## Legal / business paperwork

Two separate things, don't conflate them:
- `pages/9_📜_Legal.py` — customer-facing Terms of Service / Privacy
  Policy / Refund Policy, live in the app. Placeholders still need
  filling in (support email, governing-law state, refund window).
- `legal/` (repo root) — back-office templates (NDA, contractor
  agreement, consignment agreement, purchase agreement/bill of sale, a
  W-9 request letter, and a partnership-terms discussion checklist).
  Not shown in the app; for the owner to copy/fill in directly from the
  repo. See `legal/README.md`.

Both are explicitly marked as starting templates, not legal advice.

## Test commands

```bash
# Runtime deps are NOT preinstalled in a fresh environment; install first:
pip3 install --user pytest streamlit pandas requests httpx2 fastapi "uvicorn[standard]"

python3 -m pytest -v                 # full suite — 374 passed as of this handoff
python3 -m py_compile app.py auth.py finance.py storage.py \
    stripe_webhook_server.py $(ls pages/*.py)   # syntax check on entry points
python3 -c "import json; json.load(open('static/manifest.json'))"  # manifest sanity
```

To actually exercise the UI: `streamlit run app.py` needs
`.streamlit/secrets.toml` with at least `CRTC_ADMIN_USERNAME` /
`CRTC_ADMIN_PASSWORD_HASH` (SHA-256 hex of a password) or `require_auth()`
refuses to render anything (fails safe, by design — see `auth.py`). That
file is gitignored; never commit real credentials into it. Playwright's
Chromium is pre-installed in this environment at
`/opt/pw-browsers/chromium` — use `executable_path=` explicitly.

## Known limitations / open items (not exhaustive — see also the "OPEN
## PRODUCT REQUIREMENTS" section at the top of `CRTC_HANDOFF.md`, and
## `LAUNCH_CHECKLIST.md` for the full launch-readiness writeup)

- **Public signup isn't wired into the real login gate** — see
  "Subscription billing" above. This is the biggest open item for
  actually launching Appraze as a SaaS other people can pay for.
- **The production Streamlit Cloud app may be set to private** — a
  direct check on 2026-09-21 showed the production URL redirecting to
  Streamlit's own viewer-login gate rather than the app. Confirm/fix in
  the app's Streamlit Cloud settings before sharing any public link.
  See `LAUNCH_CHECKLIST.md` section 0.
- **`AppsScript_Code.gs` needs re-deploying** after the 2026-09-21 `plan`
  column migration, or subscription purchases won't actually save a plan
  server-side. Can't be verified from this environment (no live Apps
  Script account here) — smoke-test with a real Stripe test-mode Payment
  Link before trusting it.
- The Android CI pipeline (`.github/workflows/android-twa.yml`) failed
  on every one of its last several runs as of 2026-09-21, every time
  with **zero jobs started** — almost certainly a GitHub Actions
  billing/spending-limit block or Actions being disabled for the repo,
  not a code problem. Check that before relying on the pipeline for a
  Play Store release.
- Trademark clearance not performed (working brand only).
- F07 and F14–F17 from the simulation have no corresponding regression
  test — verify status before treating P0 as fully closed.
- Master-direction items 12 (expand adversarial testing beyond F01-F13),
  14 (dedicated security audit), 15 (AI/agent prompt-injection
  boundaries — relevant once AI listing analysis is wired to any LLM),
  and 16 (Android/iOS/Windows/Web production-readiness review) have not
  been performed in any session this repo's handoff history shows.
- Pluggable payment processor (beyond Stripe) and bring-your-own
  Anthropic API key are open owner requirements, not started (see
  `CRTC_HANDOFF.md` top section) — do not start these without checking
  they don't conflict with the "no feature creep until P0/P1 closed"
  direction; confirm F07/F14-17 status and run the item-12/14/16 reviews
  first if the owner wants the master-direction gate fully closed.
