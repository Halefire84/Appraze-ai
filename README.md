# Appraze

A single-page Streamlit dashboard for tracking, filtering, and evaluating
resale/auction deals across Estate Auctions, eBay, HiBid, Facebook
Marketplace, Mercari, Chairish, and Etsy — plus inventory, suppliers,
customers, point of sale, and an AI item analyzer.

## Run locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Deploy it / set it up for real use

See [DEPLOY.md](DEPLOY.md) — covers Streamlit Community Cloud deployment,
every optional secret (login, Google Sheets persistence, Gmail tracking,
Stripe, the AI Analyzer, support contact), and installing it as a
desktop/home-screen app.

## Tests

Pure logic (`finance.py`, `mail_parse.py`) has unit test coverage:

```bash
python3 -m unittest discover -s tests -v
```

## Project layout

- `app.py` — the Streamlit UI, all tabs
- `finance.py` — pure profit/margin/tax math, unit-tested, no Streamlit/pandas dependency
- `sheets.py` — optional Google Sheets persistence layer
- `mail_parse.py` — pure tracking-number/invoice-ref detection, unit-tested, no dependencies
- `mail.py` — optional read-only Gmail (IMAP) inbox tracking, built on `mail_parse.py`
- `static/` — PWA manifest + icons for "Install as app"
- `tests/` — unit tests
