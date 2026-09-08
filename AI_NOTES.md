# AI Coordination Notes

This repo is being worked on by more than one AI assistant at the owner's
direction (Claude, and separately Grok). There's no shared memory between
us — this file is the handoff point. If you're an AI picking up work here,
read this first. If you're the human, keep this updated when you switch
tools, since we can't see each other's sessions otherwise.

## Ground rules for anyone (AI or human) touching this repo

- **`git fetch` and check current branch state before pushing anything.**
  Several tools may be working on this repo without visibility into each
  other's changes — a stale local checkout can silently overwrite someone
  else's work.
- **Pushing to `main` auto-deploys the live Streamlit app** (see
  `DEPLOY.md`). Treat it accordingly — verify tests pass first.
- **Don't assume exclusive ownership of any file.** Check git log/blame
  before large rewrites of something you didn't just create.
- **Update this file** when you finish a chunk of work or hand off to a
  different tool, so the next session (any tool) isn't flying blind.

## Current state of `main` (as of this file's last update)

Core app: `app.py` (Streamlit) + `finance.py` (pure math, unit-tested).
Supporting modules: `auth.py` / `storage.py` (Apps Script-backed
login+persistence, see `AppsScript_Code.gs`), `billing.py` / `pos.py` /
`stripe_webhook_server.py` / `stripe_webhooks.py` / `webhook_store.py`
(Stripe paywall + POS + webhook reconciliation), `comps.py` /
`comps_adapters.py` (Market Comps engine — manual entry, CSV import, real
eBay Browse API for active listings, real eBay Marketplace Insights API
for sold comps with automatic fallback when that API isn't approved —
see below), `mail.py` / `mail_parse.py` (read-only Gmail IMAP for
supplier invoices), `drive_scan.py` (Google Drive invoice scanning),
`verdict_engine.py`. 162 tests in `tests/`, all passing.

Recent work (Claude, this session): added `voice-job-log/`, a completely
standalone dead-simple voice-note job log (single static HTML file, no
backend, no build step — browser `SpeechRecognition` API + `localStorage`).
It's unrelated to the Appraze deal-tracking app and intentionally has zero
dependency on `app.py`/`finance.py`/etc.; it's its own product living in
this repo per the branch this work was requested on. See
`voice-job-log/README.md`.

Earlier work (Claude): a no-login Demo Mode for in-person
pitching, AI Analyzer now drafts ready-to-post marketplace listings (not
just a price estimate), real eBay sold-comps lookup wired into the AI
Analyzer tab, and a fix moving every Apps Script HTTP call from GET to
POST (the old GET version put full table payloads and the auth token in
the URL query string — a real payload-size ceiling bug plus a
credential-in-logs issue; both fixed).

## Deliberately NOT built here, and why

**`web_scraper.py` / general marketplace scraping is not something Claude
built or will build in this repo.** The repo owner asked for it as a
"secondary fallback" for market comps; Claude declined because it
contradicts the project's own "official APIs only, no scraping" rule set
earlier in the same task, and because scraping marketplace sites
(eBay/Poshmark/Mercari/Facebook Marketplace) breaches their terms of
service regardless of how carefully the scraper avoids CAPTCHA-solving or
IP rotation. This is being handled by Grok instead, at the owner's
direction. Claude will not remove or rewrite that code on its own
initiative, but also won't pretend it doesn't carry real risk — see the
owner's conversation history with Claude for the specific concerns raised
(account-ban risk to the *working* eBay API integration if scraping
traffic gets attributed to the same account/IP, ToS/contract exposure,
scraper fragility, and — if it's ever merged — the need to keep it
isolated from the app's Stripe/auth secrets rather than sharing that
attack surface).

If you're integrating `web_scraper.py` into the Market Comps fallback
chain: keep it as its own adapter behind the same `CompsAdapter` protocol
already used by `ManualCompsAdapter` / `CsvCompsAdapter` / `EbayBrowseAdapter`
/ `EbayMarketplaceInsightsAdapter` in `comps_adapters.py`, tag every comp
it returns `listing_type="active"` (never `"sold"`) unless you can prove
the page is a confirmed completed sale, and don't give it access to any
secret this app already uses for something else.

## Known open items (not yet done, need a human)

- **Apps Script credential rotation.** An earlier commit checked in a
  real `TOKEN`/`SHEET_ID`/`ADMIN_SETUP_CODE` into `AppsScript_Code.gs`
  before it was replaced with placeholders — those original values are
  still recoverable from git history and should be treated as
  compromised. Only the repo owner can rotate these (requires their
  Google login) — see `AppsScript_Code.gs`'s header comment and
  `DEPLOY.md` for the redeploy steps. Still outstanding as of this
  writing.
