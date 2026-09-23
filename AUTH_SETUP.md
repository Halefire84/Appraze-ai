# CRTC Authentication Setup

CRTC uses three access paths:

1. **Shared Admin** — one owner login used by both owners. Admin data is stored in the existing shared `admin_shared` workspace.
2. **Demo** — public, no-signup sample mode. Demo data is isolated from real accounts and is never persisted to the real workspace.
3. **Tester accounts** — optional Apps Script accounts for future customers/testers.

## Shared Admin credentials

Configure these in the Streamlit deployment's secrets. **Do not put the password, password hash, Sheet token, or invite code in GitHub.**

```toml
CRTC_ADMIN_USERNAME = "admin"
CRTC_ADMIN_PASSWORD_HASH = "<bcrypt hash of your chosen production password>"
```

Generate the hash on a trusted device, then paste only the resulting hash into the Streamlit secret. Example:

```bash
python -c "import bcrypt; print(bcrypt.hashpw(b'YOUR_NEW_PASSWORD', bcrypt.gensalt()).decode())"
```

(`pip install bcrypt` first if it isn't already available — it's in `requirements.txt`.) The result looks like `$2b$12$....` — paste that whole string, including the `$2b$12$` prefix, as `CRTC_ADMIN_PASSWORD_HASH`.

Use a unique production password and do not reuse a password from another service. The development/demo bootstrap password discussed during development is **not a production credential and is intentionally not recorded in this repository**.

### Migrating an existing deployment off SHA-256

Earlier versions of this app stored `CRTC_ADMIN_PASSWORD_HASH` as a raw, unsalted SHA-256 hex digest (`hashlib.sha256(password).hexdigest()`, always 64 hex characters) and compared it directly. That scheme had no per-installation salt and was fast to brute-force offline if the hash ever leaked. `auth.py` now only accepts a **bcrypt** hash (it validates the `$2a$` / `$2b$` / `$2y$` format and rejects anything else, including an old SHA-256 hex string, as "not configured").

To migrate: generate a bcrypt hash of the **same or a new** password with the command above, and replace the `CRTC_ADMIN_PASSWORD_HASH` secret with it. There is no automatic in-place migration (the old hash cannot be converted to bcrypt without the plaintext password), so this is a manual one-time step per deployment. Until it's done, `_admin_credentials_configured()` returns `False` and the app refuses to render a login form at all (fails safe — see `require_auth()`), rather than accepting the old hash format.

### Login rate limiting

Repeated wrong passwords against the Admin account are rate-limited: after 5 consecutive failures for the same username, further attempts are locked out with exponential backoff (30s, 60s, 120s, ... capped at 15 minutes) until a correct password is entered or the backoff expires. A successful login clears the counter. This state is in-memory per running app process — it resets on a redeploy/restart, and does not span multiple app instances if the deployment ever scales beyond one.

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
