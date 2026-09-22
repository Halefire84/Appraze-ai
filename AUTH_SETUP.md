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

**Recommended: bcrypt.** Generate the hash on a trusted device, then paste only the resulting hash into the Streamlit secret:

```bash
python -c "import bcrypt; print(bcrypt.hashpw(b'YOUR_NEW_PASSWORD', bcrypt.gensalt()).decode())"
```

(`pip install bcrypt` first if it's not already available on that device.)

**Legacy: SHA-256.** A SHA-256 hex digest still works -- auth.py detects the
format automatically, so an already-deployed SHA-256 secret is not broken by
this change. New or rotated credentials should use bcrypt above; SHA-256 is
unsalted and fast to brute-force offline if the hash ever leaked, which
bcrypt is deliberately not.

```bash
python -c "import hashlib; print(hashlib.sha256(b'YOUR_NEW_PASSWORD').hexdigest())"
```

**Brute-force lockout.** Both the Admin login and tester/Apps-Script logins
lock out a username for 15 minutes after 5 failed attempts in a row
(auth.py's `_LOGIN_LOCKOUT_MAX_ATTEMPTS`/`_LOGIN_LOCKOUT_WINDOW_SECONDS`).
This is tracked in-process, so it resets on app restart/redeploy and only
applies within one running instance -- sufficient for a small beta on
Streamlit Community Cloud's single-instance free tier, not a claim of
durable, multi-instance rate limiting.

Use a unique production password and do not reuse a password from another service. The development/demo bootstrap password discussed during development is **not a production credential and is intentionally not recorded in this repository**.

## Beta invite codes (2026-09-22 beta)

A separate, small-blast-radius signup path for the beta users — deliberately not the same as opening the existing tester `signup()` to the whole internet (an open self-signup would also let anyone spin up unlimited free accounts to multiply AI-analyzer usage during the free beta). Set one secret:

```toml
CRTC_BETA_INVITE_CODES = "CODE-ONE,CODE-TWO,CODE-THREE"
```

(comma-separated, case-insensitive on entry — stored/compared upper-cased). **Do not commit real codes to this file or anywhere in git.**

Once set, the login page grows a second "Beta Sign Up" tab. Each code works exactly once — a code that's already created an account is rejected on the next attempt. Accounts are stored in a shared table (`beta_accounts`) via the same Apps Script backend `storage.py` already uses for deals/inventory (so this has the same dependency the rest of the app already has: `APPS_SCRIPT_URL`/`APPS_SCRIPT_TOKEN` must be configured and the script reachable). Beta accounts always get full free access (`is_paid=True`, `plan="beta"`) and never touch Stripe. Beta login is covered by the same brute-force lockout as Admin login (see above) — five wrong passwords against a beta account locks it out for 15 minutes too.

To turn beta signup off later, delete the `CRTC_BETA_INVITE_CODES` secret — this also blocks existing beta accounts from logging in (`_beta_login()` checks the secret is still set, same as `_beta_signup()`). If beta accounts should keep working after the beta ends while new signups stop, that needs a small follow-up change.

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
