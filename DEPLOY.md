# Deploying Appraze

Appraze is a Streamlit app. This covers getting it live on Streamlit
Community Cloud (free) and every secret it recognizes. No terminal is
required for any of this — it's all web dashboards.

## 1. Deploy the app

1. Go to [share.streamlit.io](https://share.streamlit.io) and sign in with
   the GitHub account that owns this repo.
2. Click **New app**.
3. Pick this repository, branch `main`, and main file path `app.py`.
4. Click **Deploy**. First deploy takes a minute or two while it installs
   `requirements.txt`.

Once it's deployed, every push to `main` triggers an automatic rebuild.
You can also force one anytime from the app's **⋮** menu → **Reboot app**.

## 2. Set secrets

From the app's page: **⋮** → **Settings** → **Secrets**. Paste in whichever
of these you're ready to use.

### Login + persistence (recommended before real use)

Appraze's login (sign up / log in), deal/inventory storage, and Invoice
Import Drive scanning all talk to one Google Apps Script Web App backed by
a Google Sheet — **no Google Cloud Console, no service account, no IAM at
all.**

One-time setup, entirely inside Google Sheets (works fine on mobile):
1. Create a blank Google Sheet (any name).
2. **Extensions → Apps Script**. Delete the placeholder code, paste in the
   full contents of [`AppsScript_Code.gs`](AppsScript_Code.gs) from this repo.
3. Near the top, replace `SHEET_ID`, `TOKEN`, and `ADMIN_SETUP_CODE` with
   your own values — the Sheet's ID (from its URL), a long random string of
   your own, and (optionally) a private invite code that grants admin/shared
   access to anyone who signs up with it. Treat `TOKEN` like a password.
4. **Deploy → New deployment** → gear icon → **Web app**. Set "Execute as"
   to **Me** and "Who has access" to **Anyone**. Click **Deploy**, and
   authorize it when prompted (it's your own script running on your own
   spreadsheet — the "Anyone" setting just means anyone who has the URL
   *and* your token can reach it; without the right token every request is
   rejected before it touches the sheet).
5. Copy the **Web app URL** it gives you.

Then set two Streamlit secrets:

```toml
APPS_SCRIPT_URL = "the Web app URL from step 5"
APPS_SCRIPT_TOKEN = "the same string you set as TOKEN in step 3"
```

Without these, the login gate still renders but signup/login calls will
error (the app fails safely — it never falls back to storing passwords
locally or skipping auth). Every table (Deal Dashboard, Inventory) is
stored server-side under its own key, so admins share one workspace and
every other account gets its own private, isolated storage row per table.

### Card payments — subscription paywall + POS

```toml
STRIPE_SECRET_KEY = "sk_live_... or sk_test_..."
STRIPE_PAYMENT_LINK_URL = "the Payment Link URL for app-access subscriptions"
APP_URL = "https://your-app-name.streamlit.app"
```

`STRIPE_PAYMENT_LINK_URL` gates the paywall (Payment Links only — this app
never touches raw card data, only checks payment status after the fact via
Stripe's read-only session lookup). `APP_URL` is used to build redirect URLs
for the Point-of-Sale tab's one-off checkout sessions; POS still works
without it, just with a generic redirect target.

### Automatic payment reconciliation (optional — POS tab works fine without it)

The POS tab's "Check Status" button already covers manual reconciliation
(click it after the customer pays). `stripe_webhook_server.py` is a small,
separate FastAPI service that does the same thing automatically — useful
when the customer pays on their own device/phone and nobody remembers to
click Check Status.

This runs as its **own service**, separate from the Streamlit app
(Streamlit can't receive inbound webhooks). To turn it on:

1. Deploy `stripe_webhook_server.py` somewhere that can run a small Python
   web service (Replit, Render, Fly.io, a VPS — anywhere). It needs
   `requirements-webhook.txt` installed and is started with:
   ```bash
   uvicorn stripe_webhook_server:app --host 0.0.0.0 --port 8000
   ```
2. Set these environment variables on that service (NOT in Streamlit
   secrets — this is a different process):
   ```
   STRIPE_WEBHOOK_SECRET = the signing secret from step 4 below
   APPS_SCRIPT_URL       = same value as the Streamlit secret
   APPS_SCRIPT_TOKEN     = same value as the Streamlit secret
   ```
3. Note the public URL that service gets (e.g.
   `https://your-service.example.com`).
4. In the Stripe Dashboard → **Developers → Webhooks → Add endpoint**:
   - Endpoint URL: `https://your-service.example.com/stripe/webhook`
   - Events to send: `charge.succeeded`, `charge.failed`, `charge.refunded`
   - Copy the **Signing secret** it gives you into `STRIPE_WEBHOOK_SECRET`
     above.

Once running, the POS tab's "🔄 Refresh" button picks up whatever the
webhook already confirmed — no separate UI needed. Every POS sale is
logged under one shared "sales_log" table (one shared cash register for
the whole business), so this doesn't depend on which login created the
checkout link.

### AI Analyzer / Invoice Import tabs

```toml
ANTHROPIC_API_KEY = "sk-ant-..."
```

Without it, both tabs show a "not configured yet" / error message instead
of working, rather than crashing the app.

### Market Comps tab (optional eBay active-listing search)

Manual comp entry and CSV import work with no configuration. To also pull
active eBay listings into the comps table:

```toml
EBAY_CLIENT_ID = "your eBay developer app's Client ID"
EBAY_CLIENT_SECRET = "your eBay developer app's Client Secret"
```

Get these from [developer.ebay.com](https://developer.ebay.com) → sign in
→ create an application → use the **Production** keys (client credentials
grant, no per-user OAuth needed since this only reads public listings).
Without these, the eBay search box is hidden with a "not configured"
note — manual/CSV comps still work fully.

Note: this pulls **active (asking-price) listings only**, not sold
comps — eBay's sold-listing data requires separate approved partner
access (the Marketplace Insights API) that most developer accounts don't
have. The Market Comps tab scores active-only comps at lower confidence
for exactly this reason; a sold price you look up and type in yourself is
stronger evidence than any eBay API this app can reach.

### Mail tab (supplier invoices & tracking numbers)

Without this, the Mail tab shows a "not connected" message instead of
erroring. Read-only over IMAP — Appraze never sends, replies to, deletes,
or modifies anything in the inbox.

```toml
GMAIL_ADDRESS = "the inbox to watch, e.g. chale@cooperrivertradingco.com"
GMAIL_APP_PASSWORD = "the 16-character App Password Google generated"
```

One-time setup on the Google account being watched:
1. Turn on 2-Step Verification (myaccount.google.com/security) if it isn't
   already on.
2. Create an App Password at myaccount.google.com/apppasswords (choose
   "Mail"). Paste the 16-character password it shows into
   `GMAIL_APP_PASSWORD` above — this is NOT your normal Google password.
3. Confirm IMAP is enabled: Gmail Settings (gear icon) → See all settings →
   Forwarding and POP/IMAP → Enable IMAP → Save Changes.

## 3. Install as a desktop/home-screen app (optional)

Once deployed over HTTPS, Chrome (desktop, including Windows 11) can
install the live URL as a standalone app via the install icon in the
address bar, or menu → **Cast, save and share** → **Install page as app**.
On iOS, use Safari's Share sheet → **Add to Home Screen** (Chrome on iOS
doesn't offer an equivalent).

## Running locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

Put any secrets you want available locally in `.streamlit/secrets.toml`
(same TOML format as above) — it's git-ignored, never committed.

## Security note on this repo's history

An earlier commit checked in a real `SHEET_ID`, `TOKEN`, and
`ADMIN_SETUP_CODE` directly in `AppsScript_Code.gs`. Those have since been
replaced with placeholders in the current file, but **git history still
contains the old values** — if this is that repository, treat that old
token and admin code as compromised: redeploy the Apps Script with new
values and update `APPS_SCRIPT_TOKEN` accordingly, regardless of whether
history is ever rewritten.
