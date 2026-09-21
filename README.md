# LLAVE Business OS

LLAVE is a professional retail and resale business system for tracking, filtering, and evaluating
resale/auction deals across CTBids, eBay, HiBid, Facebook Marketplace,
Mercari, Chairish, and Etsy — plus inventory margin tracking, market comps
valuation, an AI item analyzer, and Stripe point-of-sale checkout.
(`app.py`'s actual tabs, as of 2026-09-20: Deal Dashboard, Profit
Calculator, Inventory, Suppliers, Charge Customer, AI Analyzer. A few
other modules below implement invoice-import/mail-tracking features that
were built but are not currently wired into any tab — see their "NOT
CURRENTLY USED" file headers.)

## Run locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

For a full local dev setup (VS Code, Dev Containers, secrets template,
pre-push test gate, browser/mobile QA checklist), see
[LOCAL_DEV.md](LOCAL_DEV.md).

## Deploy it / set it up for real use

See [DEPLOY.md](DEPLOY.md) — covers Streamlit Community Cloud deployment
and every secret it recognizes (login/persistence, Stripe, the AI Analyzer,
Point of Sale).

## Tests

```bash
python3 -m pytest -v
```

Pure logic (`finance.py`, `mail_parse.py`, `stripe_webhooks.py`) has full
unit test coverage with no network/Streamlit dependency. `tests/test_smoke.py`
additionally verifies every production module imports cleanly and has valid
syntax.

## Project layout

- `app.py` — the Streamlit UI and production entry point (tabs: Deal
  Dashboard, Profit Calculator, Inventory, Suppliers, Charge Customer, AI
  Analyzer)
- `finance.py` — pure profit/margin/melt/tax math, the single source of
  truth for every dollar figure shown in the app; unit-tested, no
  Streamlit/pandas dependency
- `comps.py` — pure market-comps valuation math (distribution stats +
  explainable confidence rating from a list of comparable listings), then
  hands the result straight to `finance.calc_deal` so market evidence and
  the verdict math never disagree; unit-tested, no Streamlit/network
  dependency
- `comps_adapters.py` — pluggable comp sources behind one small interface:
  manual entry, CSV import (both always available), and a real eBay
  Browse API integration for active listings (needs `EBAY_CLIENT_ID`/
  `EBAY_CLIENT_SECRET` — see DEPLOY.md). Adding another source later (a
  different marketplace, a paid sold-comps feed) means writing one more
  adapter here, not touching `comps.py`'s math
- `auth.py` — signup/login against the Apps Script backend, password
  hashing, session gating
- `storage.py` — persists any named table (deals, inventory, sales_log, ...)
  per user via the same Apps Script backend
- `pos.py` — creates one-off Stripe Checkout Sessions for point-of-sale
  charges, tagged with an invoice ID; powers `app.py`'s "Charge Customer"
  tab, which also writes the resulting row into the shared `sales_log`
  table so it's reconcilable by any device or by the webhook service
- `billing.py` — `verify_checkout_session()` is `pos.py`'s manual
  "Check Status" lookup; the subscriber-paywall half of this module
  (`payment_link_url()`) is unrelated and still unused, see below
- `stripe_webhooks.py` — pure, unit-tested Stripe webhook signature
  verification + event handling
- `stripe_webhook_server.py` / `webhook_store.py` — the small standalone
  FastAPI service (deployed separately from Streamlit) that receives those
  webhooks and reconciles POS sales automatically; see DEPLOY.md
- `AppsScript_Code.gs` — the Apps Script backend `auth.py`/`storage.py`
  talk to; paste into a Sheet's Extensions → Apps Script (see DEPLOY.md —
  replace the placeholder `SHEET_ID`/`TOKEN`/`ADMIN_SETUP_CODE` with your
  own before deploying)
- `static/` — PWA manifest + icons for "Install as app"
- `tests/` — unit tests

### Built but not currently wired into `app.py` (marked "NOT CURRENTLY
USED" in each file's own header as of 2026-09-20 — kept rather than
deleted; see `CRTC_HANDOFF.md` for the full inventory)

- `billing.py`'s subscriber-paywall flow (`payment_link_url()` + the
  Payment-Link redirect it describes) — `app.py` has no paywall logic
  today. (`verify_checkout_session()` in the same file *is* used, by
  `pos.py` — see above.)
- `drive_scan.py` — scans a named Google Drive folder for new invoice
  files via the Apps Script backend
- `mail.py` / `mail_parse.py` — read-only Gmail tracking of supplier
  invoices/shipments; no Mail tab exists in `app.py`. `mail_parse.py`'s
  parsing logic is real and unit-tested even though its only caller isn't
  wired in
- `crtc.py` — an earlier Cross-List prototype, superseded by
  `pages/5_🔗_Cross_List.py`
- `financial_intelligence.py` / `payments_adapter.py` — provider-neutral
  scaffolding for a planned future Plaid/Venmo/PayPal integration (see
  `CRTC_FINANCIAL_ROADMAP.md`), not yet built upon
- `crtc_learning.py` — outcome-tracking/learning-loop module, tested but
  not yet wired into Opportunity Radar (see `docs/CRTC_CONTINUOUS_HUNT.md`)
- `ebay_image_scan.py` — hardened eBay search-by-image adapter, tested,
  intentionally not yet called from any page (recent work, not legacy)

Note: `verdict_engine.py`, previously listed here, was removed from the
repo entirely (commit `7aae182`) — this file no longer exists.
