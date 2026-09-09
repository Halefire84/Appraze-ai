# CRTC Authentication Setup

CRTC uses three access paths:

1. **Shared Admin** — one owner login used by both owners. Admin data is stored in the existing shared `admin_shared` workspace.
2. **Demo** — public, no-signup sample mode. Demo data is isolated from real accounts and is never persisted to the real workspace.
3. **Tester accounts** — optional Apps Script accounts for future customers/testers.

## Shared Admin credentials

Configure these in the Streamlit deployment's secrets. Do **not** put the password or its hash in GitHub.

```toml
CRTC_ADMIN_USERNAME = "admin"
CRTC_ADMIN_PASSWORD_HASH = "<SHA-256 hash of your chosen password>"
```

For the requested initial password `Changeme`, the correct SHA-256 hash is:

`9370287b2e0de984e2a3b46a2f5841f2fd843a376a7a014f2598ac85ebac232b`

**Important:** `Changeme` is a temporary bootstrap password, not a production password. Change it before public launch. Never commit the plaintext password or the hash to source control.

### Android-friendly way to generate a new hash

If you have Python/Termux available:

```bash
python -c "import hashlib; print(hashlib.sha256(b'YOUR_NEW_PASSWORD').hexdigest())"
```

Then put the resulting value in your Streamlit secrets.

## Demo

The existing app already has a demo route:

- `?demo=1` opens demo mode directly.
- The login page has **Try Live Demo**.

Demo mode must remain isolated from `auth.py`, `storage.py`, and the real Admin workspace. It is intended for prospective customers to explore CRTC without creating an account.

## Production rule

The shared Admin username/password is intentionally simple for the two owners, but the credential must live in deployment secrets, not source control. Never commit `Changeme`, an admin password, or an admin password hash to GitHub.
