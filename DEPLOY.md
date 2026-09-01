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
of these you're ready to use — every one is optional, and the app runs
fine with none of them set (it just falls back to a placeholder / shows a
"not configured" warning on the relevant tab).

### Login (pick one)

Single shared password — everyone sees the same data:

```toml
APP_PASSWORD = "whatever you pick"
```

Or multiple isolated testers — each password gets its own separate,
invisible-to-the-others copy of every table (deals, inventory, suppliers,
customers, sales log). Takes priority over `APP_PASSWORD` when set:

```toml
APP_PASSWORDS = { a = "password1", b = "password2", c = "password3", d = "password4" }
```

⚠️ **Use that one-line form, not a bracketed `[APP_PASSWORDS]` section.**
In TOML, a `[section]` header silently swallows every `key = value` line
pasted after it into that section — so if you paste `GOOGLE_SHEET_ID`,
`STRIPE_SECRET_KEY`, etc. below a bracketed `[APP_PASSWORDS]` block (the
natural thing to do, copying this doc top-to-bottom into one secrets box),
those secrets vanish into `APP_PASSWORDS` instead of being read as their
own secrets. Every other feature in the app would then look "not
configured" with **no error anywhere** — this exact mistake is a common
cause of "my testers' accounts don't seem connected to anything." The
one-line form above avoids the trap entirely; if you ever paste a
bracketed `[APP_PASSWORDS]` section instead, the sidebar will flag it for
you after you log in with a "Secrets misconfigured" warning naming exactly
which secrets got swallowed.

If neither is set, the login password defaults to `changeme` — set one
before sharing the link.

### Persistence (optional, strongly recommended before real use)

Without this, all data lives only in each browser session and resets on
every reload or app restart. See `sheets.py`'s docstring for the full
one-time Google Cloud setup (create a project, enable the Sheets + Drive
APIs, create a service account, download its JSON key, share a spreadsheet
with it). Once you have those:

```toml
GOOGLE_SHEET_ID = "the spreadsheet ID from its URL"
GOOGLE_SERVICE_ACCOUNT_JSON = '''{ ...full service-account JSON key... }'''
```

With multi-tester login (`APP_PASSWORDS`) also configured, each tester's
data lands in its own worksheet tabs inside that one spreadsheet (e.g.
`deals__a`, `deals__b`), so you can watch everyone's data live without it
colliding.

### Mail tab (supplier invoices & tracking numbers)

Without this, the Mail tab shows a "not connected" message instead of
erroring. See `mail.py`'s docstring for the full one-time Gmail setup
(turn on 2-Step Verification, create an App Password, confirm IMAP is
enabled). Once you have those:

```toml
GMAIL_ADDRESS = "the inbox to watch, e.g. chale@cooperrivertradingco.com"
GMAIL_APP_PASSWORD = "the 16-character App Password Google generated"
```

This connects read-only over IMAP — Appraze never sends, replies to,
deletes, or modifies anything in the inbox.

It's one shared inbox for the whole app (not a separate one per
`APP_PASSWORDS` tester), so it only shows up in the workspace named
`"business"` by default — every other workspace sees "not available on
this deployment" instead of the owner's real email. If your own workspace
in `APP_PASSWORDS` is named something else (e.g. `owner`), set:

```toml
MAIL_WORKSPACE = "owner"
```

### Card payments (Point of Sale tab)

```toml
STRIPE_SECRET_KEY = "sk_live_... or sk_test_..."
```

Without it, Card is disabled with an explanatory message; Cash still
works.

### AI Analyzer tab

```toml
ANTHROPIC_API_KEY = "sk-ant-..."
```

Without it, the tab shows a "not configured yet" message instead of
erroring.

### Support contact

```toml
SUPPORT_EMAIL = "you@example.com"
```

Shown in the sidebar. Without it, the sidebar shows a placeholder telling
you to set this secret.

## 3. Install as a desktop/home-screen app (optional)

Once deployed over HTTPS, Chrome (desktop, including Windows 11) can
install the live URL as a standalone app via the install icon in the
address bar, or menu → **Cast, save and share** → **Install page as app**.
On iOS, use Safari's Share sheet → **Add to Home Screen** (Chrome on iOS
doesn't offer an equivalent). See `app.py`'s PWA manifest section for how
this is wired up.

## Running locally (optional)

```bash
pip install -r requirements.txt
streamlit run app.py
```

Put any secrets you want available locally in `.streamlit/secrets.toml`
(same TOML format as above) — it's git-ignored, never committed.
