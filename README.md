# Appraze

A single-page Streamlit dashboard for tracking, filtering, and evaluating
resale/auction deals across CTBids, eBay, HiBid, Facebook Marketplace,
Mercari, Chairish, and Etsy — plus inventory margin tracking, an AI item
analyzer, invoice import, mail tracking, and point-of-sale checkout.

## Run locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

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

- `app.py` — the Streamlit UI and production entry point (all tabs: Deal
  Dashboard, Inventory, Profit Calculator, Melt Calculator, AI Analyzer,
  Invoice Import, Mail, POS Checkout)
- `finance.py` — pure profit/margin/melt/tax math, the single source of
  truth for every dollar figure shown in the app; unit-tested, no
  Streamlit/pandas dependency
- `auth.py` — signup/login against the Apps Script backend, password
  hashing, session gating
- `storage.py` — persists any named table (deals, inventory, sales_log, ...)
  per user via the same Apps Script backend
- `billing.py` — verifies Stripe Payment Link checkout sessions (subscriber
  paywall)
- `pos.py` — creates one-off Stripe Checkout Sessions for point-of-sale
  charges, tagged with an invoice ID the webhook service reconciles later
- `drive_scan.py` — scans a named Google Drive folder for new invoice
  files via the same Apps Script backend
- `stripe_webhooks.py` — pure, unit-tested Stripe webhook signature
  verification + event handling
- `stripe_webhook_server.py` / `webhook_store.py` — the small standalone
  FastAPI service (deployed separately from Streamlit) that receives those
  webhooks and reconciles POS sales automatically; see DEPLOY.md
- `verdict_engine.py` — standalone deterministic buy/pass scorer with its
  own risk/confidence model; not currently called from `app.py`
- `mail.py` / `mail_parse.py` — read-only Gmail tracking of supplier
  invoices/shipments, powering the Mail tab; parsing logic is unit-tested
- `AppsScript_Code.gs` — the Apps Script backend `auth.py`/`storage.py`/
  `drive_scan.py` talk to; paste into a Sheet's Extensions → Apps Script
  (see DEPLOY.md — replace the placeholder `SHEET_ID`/`TOKEN`/
  `ADMIN_SETUP_CODE` with your own before deploying)
- `static/` — PWA manifest + icons for "Install as app"
- `tests/` — unit tests
