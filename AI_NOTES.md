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

## Current state of `main` (last corrected 2026-09-20 — this section had
drifted: it listed `verdict_engine.py`, which was deleted in commit
`7aae182` and no longer exists, described several modules as active
features that current `app.py` doesn't actually wire in, and its test
count was stale. If you're an AI/human about to trust a summary here,
cross-check it against `git log`/`grep` first — this file is exactly as
capable of going stale as any other doc, as this correction proves.)

Core app: `app.py` (Streamlit) + `finance.py` (pure math, unit-tested).
`app.py`'s actual tabs today: Deal Dashboard, Profit Calculator,
Inventory, Suppliers, Charge Customer, AI Analyzer — no Mail, Invoice
Import, or POS Checkout tab exists despite some module docstrings
describing those as current features.

Supporting modules actually wired in: `auth.py` / `storage.py`
(Apps Script-backed login+persistence, see `AppsScript_Code.gs`),
`stripe_webhook_server.py` / `stripe_webhooks.py` / `webhook_store.py`
(standalone webhook-reconciliation service, separate from `app.py`),
`comps.py` / `comps_adapters.py` (Market Comps engine — manual entry, CSV
import, real eBay Browse API for active listings, real eBay Marketplace
Insights API for sold comps with automatic fallback when that API isn't
approved), plus the full Opportunity Radar / Holy Grail / flip-lifecycle
module set under `pages/`.

Built but NOT wired into any tab/page as of 2026-09-20 (each now says so
in its own file header — see `README.md`'s "Built but not currently
wired" section and `CRTC_HANDOFF.md` for the full inventory and why):
`billing.py`, `pos.py`, `mail.py` / `mail_parse.py`, `drive_scan.py`,
`crtc.py` (superseded by `pages/5_🔗_Cross_List.py`),
`financial_intelligence.py` / `payments_adapter.py` (future-roadmap
scaffolding, see `CRTC_FINANCIAL_ROADMAP.md`), `crtc_learning.py` (tested,
tied to `docs/CRTC_CONTINUOUS_HUNT.md`'s design), `ebay_image_scan.py`
(recent, deliberate, not legacy). None were deleted — this environment
treats file deletion as a destructive action needing explicit user
confirmation — they're marked instead so nobody mistakes them for live
code.

300 tests in `tests/` as of 2026-09-20 (`python3 -m pytest tests/ -q`),
all passing — re-run this yourself before trusting the number; it will
drift the moment either of us adds more.

Recent work (Claude): a no-login Demo Mode for in-person pitching, AI
Analyzer now drafts ready-to-post marketplace listings (not just a price
estimate), real eBay sold-comps lookup wired into the AI Analyzer tab, a
fix moving every Apps Script HTTP call from GET to POST, Stripe webhook
replay-protection (timestamp tolerance), a real PWA manifest `<head>`
link, hardened `ebay_image_scan.py`, a testable AI listing-enrichment
abstraction in `listing_bridge.py`, rich eBay listings preserved through
`opportunity_sources.scan_ebay_active()` instead of collapsing to a
single blank `source_listing_id`, and this file-inventory correction.

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
