# Appraze

**Complete Resale Business Suite**

*Deal math, inventory, and listing for resellers.*

Appraze is the customer-facing product from **Cooper River Trading Co. (CRTC)**. It brings deal analysis, profit math, inventory, valuation, listing workflows, payments, and resale operations into one workspace.

## Run locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Deploy

See [DEPLOY.md](DEPLOY.md) for Streamlit deployment, secrets, authentication, Stripe, AI Analyzer, and point-of-sale configuration.

## Tests

```bash
python3 -m pytest -v
```

The repository contains unit tests for core finance, authentication, payment, webhook, storage, and application logic.

## Product

- Deal analysis and profit math
- Inventory and margin tracking
- Market-comps valuation
- AI item analysis and listing drafts
- Stripe point-of-sale checkout
- Customer accounts, quotes, invoices, and payments
- Marketplace-ready listing workflows

## Brand

**Appraze** is the product.

**Cooper River Trading Co. (CRTC)** is the company.

The GitHub repository remains `Appraze-ai` for technical continuity.
