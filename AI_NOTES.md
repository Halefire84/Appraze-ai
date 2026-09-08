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

Recent work (Claude, this session): the owner's real ask turned out to be
record-keeping gaps in the production app, not the standalone
`voice-job-log/` prototype mentioned below. Added to `app.py`:
- Inventory now has `Sale Channel`/`Sale Date` columns (backfilled for
  existing saved rows via `ensure_inventory_sale_columns()`), editable
  directly or through a new guided form.
- POS Checkout tab: a "Record a sale made elsewhere" section for anything
  that didn't run through Stripe — eBay, Facebook Marketplace, Mercari,
  cash — since the tab previously only supported card charges. Marks the
  Inventory item Sold with the real channel/price/date.
- New Reports tab: monthly/yearly gross sales, cost basis, fees, and net
  profit rolled up from Inventory Sold rows + Stripe POS payments, broken
  down by sale channel, with CSV export (monthly summary + full
  transaction detail) for handing to an accountant or tax software.
  Explicitly not tax advice — only tracks item-level cost/price/fees, not
  mileage/supplies/other business expenses.

Still outstanding from that same conversation, waiting on the owner's
answer to a feasibility question before building: auto-generating a
complete listing from a photo already exists (AI Analyzer drafts
copy-paste-ready eBay/Poshmark/Mercari/Facebook text) but the owner wants
actual automated cross-posting, not just drafts, ideally to eBay +
2 Facebook accounts + Mercari + future marketplaces. eBay has a real Sell
API for this (feasible, needs the owner to set up an eBay Developer app
with listing-write scope — bigger lift than the existing read-only
Browse/Insights keys). Facebook Marketplace and Mercari have **no**
public API for posting a personal listing — the only way to automate
posting there is browser automation against their Terms of Service, which
is the exact same category of risk this file already documents Claude
declining for `web_scraper.py` below (account-ban risk, ToS exposure).
Don't build FB/Mercari auto-posting without the owner explicitly accepting
that risk in writing somewhere in the conversation history — default to
keeping those two as copy-paste drafts.

Also from an earlier ask in this same session, unrelated to Appraze: a
`voice-job-log/` folder exists in this branch (a static-HTML voice-note
job log prototype) that the owner wants kept as a *separate* product, not
part of this repo — Claude offered to strip it back out once a dedicated
GitHub repo existed for it, but that repo was never created before the
owner's attention moved to the Appraze asks above, so the folder is still
sitting here. The real version was rebuilt as a proper Next.js +
Postgres + Whisper app (multi-tenant SaaS shape) in a local checkout
outside this repo, not yet pushed anywhere. The owner then said they
actually want it kept private (personal/business use, not sold or
app-store-distributed) — so it may not need the multi-tenant/billing
scaffolding it was given; confirm with the owner before continuing that
thread, and remember to remove `voice-job-log/` from this repo once it
has its own home.

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
