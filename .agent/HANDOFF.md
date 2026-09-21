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

## Branding — settled 2026-09-21 (see `APPRAZE_BRAND.md`)

Product name is **Appraze**, spelled A-p-p-r-a-z-e (not "appraise").
"BUSINESS OS" / "LLAVE" / "TURNKEY" are all retired working names from an
earlier multi-day rebrand saga — do not reintroduce them. `CRTC_NAME.md`
and `BUSINESS_OS_BRAND.md` are superseded history, not current direction.
Real Appraze wordmark/icon assets have **not** been supplied yet — the
PWA manifest and sidebar currently use a generic placeholder icon
(`static/icon-192.png` etc.). Wire in the real logo when it arrives and
update `APPRAZE_BRAND.md`'s visual-direction section.

This session (2026-09-21) also added: Appraze™ trademark marks on the
first prominent mention per screen, a memorial dedication (comment header
block in every entry-point module + an "In Memory" section on a new
About tab in `app.py`), non-functional build-provenance watermark
constants (`_APPRAZE_BUILD_ATTRIBUTION`) in `finance.py`/`storage.py`/
`app.py` with a playful non-blocking tamper banner, and a hidden easter
egg (typing "christopher hale" into the Deal Dashboard search box). None
of this touched financial/business logic. Full detail in `CRTC_HANDOFF.md`
under "2026-09-21 — Final rebrand to Appraze™...".

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
`python3 -m pytest -v` (367 tests, includes all of the above) stays green
before and after the branding changes. Do not assume the full 20-item
master-direction quality gate (security audit, mobile/Windows/web
production-readiness review, etc.) is complete just because these tests
pass — see "Still open" below.

## Test commands

```bash
# Runtime deps are NOT preinstalled in a fresh environment; install first:
pip3 install --user pytest streamlit pandas requests httpx2 fastapi "uvicorn[standard]"

python3 -m pytest -v                 # full suite — 367 passed as of this handoff
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
## PRODUCT REQUIREMENTS" section at the top of `CRTC_HANDOFF.md`)

- Real Appraze logo/wordmark assets not yet supplied.
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
