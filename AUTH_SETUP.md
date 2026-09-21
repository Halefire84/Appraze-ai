# CRTC Authentication Setup

CRTC uses four access paths:

1. **Shared Admin** — one owner login used by both owners. Admin data is stored in the existing shared `admin_shared` workspace.
2. **Demo** — public, no-signup sample mode. Demo data is isolated from real accounts and is never persisted to the real workspace.
3. **Beta invite codes** — the path used for the 2026-09-22 beta. See below.
4. **Tester accounts** — optional Apps Script accounts for future customers/testers (`auth.signup()`/`auth.login()`); not currently reachable from any page, kept for later.

## Shared Admin credentials

Configure these in the Streamlit deployment's secrets. **Do not put the password, password hash, Sheet token, or invite code in GitHub.**

```toml
CRTC_ADMIN_USERNAME = "admin"
CRTC_ADMIN_PASSWORD_HASH = "<bcrypt hash of your chosen production password>"
```

Generate the hash on a trusted device, then paste only the resulting hash into the Streamlit secret:

```bash
python3 -c "import bcrypt; print(bcrypt.hashpw(b'YOUR_NEW_PASSWORD', bcrypt.gensalt()).decode())"
```

(needs `pip install bcrypt` on whatever machine you run this on — it's
already in `requirements.txt` for the deployed app itself.)

Use a unique production password and do not reuse a password from another service. The development/demo bootstrap password discussed during development is **not a production credential and is intentionally not recorded in this repository**.

**Migrating an existing deployment (2026-09-21):** the Admin password
check now uses bcrypt instead of unsalted SHA-256, which is meaningfully
safer if the stored hash ever leaked. This is backward compatible — an
already-configured `CRTC_ADMIN_PASSWORD_HASH` secret (the old SHA-256
hex format) keeps working exactly as before, nothing breaks on deploy.
When convenient, regenerate it with the bcrypt command above and update
the secret to get the stronger hash; there's no forced cutover date.

## Beta invite codes (2026-09-22 beta)

A separate, small-blast-radius signup path for the ten beta users — deliberately not the same as opening the existing tester `signup()` to the whole internet. Set one secret:

```toml
CRTC_BETA_INVITE_CODES = "CODE-ONE,CODE-TWO,CODE-THREE"
```

(comma-separated, case-insensitive on entry — stored/compared upper-cased). The actual ten codes for tomorrow are in `reports/latest-session-report.md` (gitignored — never committed) or the terminal output from the session that generated them. **Do not commit real codes to this file or anywhere in git.**

Once set, the login page grows a second "Beta Sign Up" tab. Each code works exactly once — a code that's already created an account is rejected on the next attempt. Accounts are stored in a shared table (`beta_accounts`) via the same Apps Script backend `storage.py` already uses for deals/inventory (so this has the same dependency the rest of the app already has: `APPS_SCRIPT_URL`/`APPS_SCRIPT_TOKEN` must be configured and the script reachable). Beta accounts always get full free access (`is_paid=True`, `plan="beta"`) and never touch Stripe — there's no plan-based feature gating anywhere in the app today, so this alone is sufficient; nothing needs to be separately "unlocked."

To turn beta signup off later, delete the `CRTC_BETA_INVITE_CODES` secret — this also blocks existing beta accounts from logging in (`_beta_login()` checks the secret is still set, same as `_beta_signup()`). If beta accounts should keep working after the beta ends while new signups stop, that needs a small follow-up change — not needed for tomorrow.

## Demo

The existing app has a demo route:

- `?demo=1` opens demo mode directly.
- The login page has **Try Live Demo**.

Demo mode must remain isolated from `auth.py`, `storage.py`, and the real Admin workspace. It is intended for prospective customers to explore CRTC without creating an account.

## Production security rules

- Shared Admin credentials live only in deployment secrets.
- Never commit an Admin password or password hash.
- Never commit Apps Script `TOKEN`, `SHEET_ID`, or `ADMIN_SETUP_CODE` values.
- Rotate any credential that was ever committed to git history before production use.
- Keep Demo mode free of real customer/business data and real payment actions.
- If the production Admin credential is ever shared outside the two owners, rotate it immediately.
- Never commit real `CRTC_BETA_INVITE_CODES` values to git — same rule as any other credential.

## Visit counter & feedback (2026-09-22 beta)

Two more small shared tables via the same Apps Script backend, no extra secrets needed:

- `visit_counter` — a rough total-visits count, incremented once per browser session the moment `require_auth()` runs (see `auth._record_visit_once()`), shown to Admin on the Feedback page.
- `beta_feedback` — free-text bug reports/feedback any logged-in user (Admin or beta) can submit from the 🐛 Feedback page, also shown to Admin on that same page.

Both fail silently on any storage error rather than blocking login or the page — worst case they just don't count/save that one event.
