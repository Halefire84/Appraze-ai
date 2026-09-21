# Appraze™ / CRTC — Agent Handoff

Read this first. It is meant to stand on its own, without conversation
history. For deep narrative detail on any item below, see
`CRTC_HANDOFF.md` (chronological session log, ~900 lines),
`APPRAZE_BRAND.md` (brand record), `COMPETITIVE-GAPS.md` (sourced
market research), and `DOMINANCE-ROADMAP.md` (proposed differentiators,
not yet built).

## Repo visibility

The GitHub repo was public through 2026-09-21 and the owner was advised
to switch it to private (source contains real competitive-advantage
logic now) — **confirm it's actually private** before assuming any
secrecy about pricing logic, decision math, or the roadmap doc holds.
Note: private repos get a limited monthly GitHub Actions minutes
allowance vs. unlimited on public — relevant to the Android CI issue
below.

## Business/monetization posture — read before touching Pricing or auth

The owner's explicit instruction (2026-09-21): **do not take this live
for real customers or push monetization until the product is verified
"better than good."** Nothing today enables public signup or removes
that gate — see "Subscription billing" below, which is *still* blocked
on the same auth-gate issue as before. Don't wire public signup as a
side effect of some other task without this being the explicit ask.

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

**Update, 2026-09-21 late (beta-access sprint): `require_auth()` now
also supports a second, narrower path — invite-code-gated beta signup —
see the new section below. `auth.signup()` / `render_login_gate()`
(the original public tester signup/login) are still real, unit-tested,
dead code — still nothing calls them from any page.** Beta accounts are
a deliberately smaller mechanism (ten single-use codes, not an open
public signup form) built to unblock a specific 10-person beta with a
hard next-day deadline; they are NOT the same thing as real multi-tenant
public signup. If the intent afterward is a real public SaaS signup
(which the Pricing page, the public landing artifact, and
`pages/9_📜_Legal.py`'s Terms of Service all already assume), **wiring
`auth.signup()`/`render_login_gate()` (or a hardened equivalent) into
the real entry point is still the next concrete step** — and it's its
own scope (workspace/data isolation for a new signup, whether Free-tier
limits are actually enforced anywhere, rate-limiting/abuse prevention
now that anyone with the URL could reach a signup form, etc.), not
something to bolt on casually. See `LAUNCH_CHECKLIST.md` section 2 for
the full writeup.

Also still true: `subscription_plans.feature_enabled()` exists and is
unit-tested, but nothing in the app calls it — buying a plan today
records the purchase but doesn't unlock or restrict anything yet.

## Beta access, feedback, visit counter — 2026-09-21 late (beta-access sprint)

Built same-night for a 2026-09-22 beta with 10 real users, on top of an
Admin-only bcrypt-hardened login (see previous section's history and
`AUTH_SETUP.md` for the SHA-256→bcrypt migration, backward compatible,
no forced cutover).

- **Beta invite codes**: `CRTC_BETA_INVITE_CODES` secret (comma-separated)
  turns on a "Beta Sign Up" tab in `require_auth()`. Each code is
  single-use. Accounts persist to a shared `beta_accounts` table via the
  same Apps Script `save_data`/`load_data` backend `storage.py` already
  uses — no new external dependency. bcrypt passwords from the start (no
  legacy path needed, these are new accounts). Beta accounts get
  `is_paid=True`/`plan="beta"` and never call `mark_paid()`/touch
  Stripe — full free access, and since there's no plan-based feature
  gating anywhere in the app yet, that's sufficient on its own. See
  `auth._beta_signup()`/`_beta_login()`/`_beta_enabled()`.
- **Why invite codes and not wiring the existing public `signup()`**:
  smaller blast radius under time pressure — only someone holding one of
  ten codes can ever create an account, versus opening a signup form (with
  its own unaudited-tonight SHA-256 path) to the whole internet. Reuses
  proven storage instead of inventing a new persistence mechanism.
- **Known limitation**: two people redeeming different codes in the same
  instant could race on the shared accounts table (last-write-wins, same
  tradeoff `storage.py`'s own docstring already accepts for a
  solo/small-team tool) — fine for 10 people over one day, not for real
  scale. If beta signup needs to stay open longer or scale up, this
  should move to something with real write serialization.
- **Visit counter**: `auth._record_visit_once()`/`get_visit_count()` — a
  rough, best-effort total-visits count (one shared `visit_counter`
  table, same backend), incremented once per browser session the moment
  `require_auth()` runs, whether or not the visitor ever logs in. Fails
  silently on any storage error — never blocks login.
- **Feedback**: `pages/10_🐛_Feedback.py` — any logged-in user (beta or
  Admin) can submit a free-text bug report/feedback message, appended to
  a shared `beta_feedback` table (same backend again). Admin sees total
  visits and the full feedback log on the same page. Readable straight
  out of the Google Sheet too, no dashboard needed.
- **Deploy blocker still open**: none of this reaches production until
  `claude/continue-from-yesterday-3zx97l` (or its changes) lands on
  `main` — Streamlit Cloud auto-deploys from `main` only. Not resolved
  this session; needs the repo owner's explicit call (see
  `reports/latest-session-report.md`, gitignored, for the live invite
  codes and full session writeup — do not put real invite codes in this
  file or anywhere else in git).
- **Streamlit Cloud public/private setting**: still unverified this
  session too — no dashboard access from this environment. Check
  Settings → Sharing before beta.

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

## Pricing tiers, competitive research, and UI theme — 2026-09-21 (second half of the day)

- Pricing renamed/restructured: "Hunter" → **"Appraiser"** (flagship,
  now $59/mo, key `"appraiser"` not `"hunter"` in `subscription_plans.py`
  — if you're grepping for the old key you'll find nothing), and a new
  **"Analyst"** tier ($35/mo) added between Scout and Appraiser. Round-
  dollar pricing (no `.99`) is a deliberate, documented brand choice —
  see the module docstring in `subscription_plans.py` before "fixing"
  it back to `.99` pricing.
- `COMPETITIVE-GAPS.md` — sourced research on 7 named competitors
  (pricing, features, complaints, core user), plus a ranked "where they
  all bleed" section. Every claim is sourced or marked UNKNOWN. Use this
  before making any other pricing/positioning claim rather than
  guessing.
- `DOMINANCE-ROADMAP.md` — 5 proposed differentiators (ranked
  recommendation: Outcome Learning Loop → Photo-to-Verdict Loop →
  Probabilistic Profit Distributions, with Estate-Sale Field Mode and an
  AI Sourcing Agent queued behind those). **Proposal only — not built.**
  Don't start building any of it without the owner picking a direction
  first; three major unreviewed features going in at once is exactly
  the risk this repo's P0-first pattern exists to avoid.
- **`ui_theme.py`** is now the one place app-wide styling lives —
  `inject_theme()`, called right after `st.set_page_config()` on every
  page including `app.py` itself. There *was* a real bug here: styling
  used to live only in `app.py`'s own script, so any page opened
  directly (a bookmark, a shared link, a fresh tab) — never having run
  `app.py` first — got none of it. Confirmed both the bug and the fix
  with a direct-navigation Playwright test. If you add a new page, call
  `inject_theme()` on it or it'll look like unstyled default Streamlit.
- `.streamlit/config.toml` now sets `toolbarMode = "minimal"` (hides
  Streamlit's own Deploy button/hamburger menu) and a `[theme]` block
  matching the brand palette — this is most of what stopped the app
  from reading as "a webpage."

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

- **Real public signup still isn't wired into the login gate** — see
  "Subscription billing" and "Beta access, feedback, visit counter"
  above. Beta invite codes (2026-09-21 late) unblock a 10-person beta
  only; they are not open public signup. This is still the biggest open
  item for actually launching Appraze as a SaaS anyone can pay for.
- **The production Streamlit Cloud app may be set to private** — a
  direct check on 2026-09-21 showed the production URL redirecting to
  Streamlit's own viewer-login gate rather than the app. Still
  unverified as of 2026-09-21 late (no Streamlit Cloud dashboard access
  from this environment either session). Confirm/fix in the app's
  Streamlit Cloud settings before sharing any public link. See
  `LAUNCH_CHECKLIST.md` section 0.
- **None of tonight's (2026-09-21 late) work is deployed** —
  `claude/continue-from-yesterday-3zx97l` is pushed but not merged to
  `main`, and Streamlit Cloud auto-deploys from `main` only. This is the
  actual blocker for tomorrow's beta functioning at all; resolving it
  needs the repo owner's explicit go-ahead (never pushed to `main`
  unilaterally — see this session's branch policy).
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
