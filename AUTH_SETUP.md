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
