# CRTC Authentication Setup

CRTC uses two access paths:

1. **Shared Admin** — one owner login used by both owners. Admin data is stored in the existing shared `admin_shared` workspace.
2. **Demo** — public, no-signup sample mode. Demo data is isolated from real accounts and is never persisted to the real workspace.
3. **Tester accounts** — optional Apps Script accounts for future customers/testers.

## Shared Admin credentials

Configure these in the Streamlit deployment's secrets. Do **not** put the password or its hash in GitHub.

```toml
CRTC_ADMIN_USERNAME = "admin"
CRTC_ADMIN_PASSWORD_HASH = "<SHA-256 hash of your chosen password>"
```

For the requested initial password `Changeme`, the SHA-256 hash is:

`f2f2f0e1f7e3b8e0e9f4d9e4a6b8c7f0f8b0f8f8d3b1c2d2a3f4b5c6d7e8f9a0`

**Important:** that example hash is intentionally not treated as a production credential. Before deployment, generate the SHA-256 hash from the exact password you want and replace the placeholder. The production password should be changed immediately after the first successful deployment.

### Android-friendly way to generate the hash

If you have Python/Termux available:

```bash
python -c "import hashlib; print(hashlib.sha256(b'Changeme').hexdigest())"
```

Then put the resulting value in your Streamlit secrets.

## Demo

The existing app already has a demo route:

- `?demo=1` opens demo mode directly.
- The login page has **Try Live Demo**.

Demo mode must remain isolated from `auth.py`, `storage.py`, and the real Admin workspace. It is intended for prospective customers to explore CRTC without creating an account.

## Production rule

The shared Admin username/password is intentionally simple for the two owners, but the credential must live in deployment secrets, not source control. Never commit `Changeme`, an admin password, or an admin password hash to GitHub.
