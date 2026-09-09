# CRTC Production Security Release Checklist

Use this checklist immediately before the first public production launch of CRTC.

## 1. Rotate historically exposed credentials

The repository previously contained real Google Apps Script deployment values in git history. Treat those historical values as compromised.

- [ ] Create a new Google Sheet token.
- [ ] Create a new private Admin invite/setup code, or leave admin signup disabled.
- [ ] Replace the Apps Script placeholders with the new values in the private Apps Script deployment (not this repository).
- [ ] Redeploy the Apps Script Web App.
- [ ] Put the new Apps Script URL/token into Streamlit secrets.
- [ ] Revoke/retire the old token and old invite code.

## 2. Configure the shared owner Admin

CRTC intentionally uses one shared Admin workspace for the two owners.

Required Streamlit secrets:

```toml
CRTC_ADMIN_USERNAME = "admin"
CRTC_ADMIN_PASSWORD_HASH = "<SHA-256 hash of a NEW production password>"
```

- [ ] Use a unique production password; do not use the development/demo password `Changeme`.
- [ ] Store only the SHA-256 hash in Streamlit secrets.
- [ ] Confirm Admin login maps to `admin_shared` and both owners see the same workspace.
- [ ] Confirm an ordinary tester account cannot access Admin data.

## 3. Verify Demo isolation

- [ ] `?demo=1` opens Demo mode without authentication.
- [ ] Demo data is sample-only.
- [ ] Demo actions do not call real storage or payment systems.
- [ ] Exiting Demo returns to the normal login path.

## 4. Verify integrations

Configure only the services actually being used:

- [ ] `APPS_SCRIPT_URL`
- [ ] `APPS_SCRIPT_TOKEN`
- [ ] `ANTHROPIC_API_KEY`
- [ ] `EBAY_CLIENT_ID`
- [ ] `EBAY_CLIENT_SECRET`
- [ ] Stripe secrets if POS/payment features are enabled
- [ ] Gmail app password if Mail/Drive workflows are enabled

Do not place any of these values in source files, README files, screenshots, issues, or commits.

## 5. Holy Grail Finder data policy

CRTC may combine official APIs, permitted public data, feeds, exports, and user-provided listings.

- [ ] Do not bypass CAPTCHA, bot controls, authentication walls, or rate limits.
- [ ] Do not present active asking prices as sold prices.
- [ ] Do not fabricate sold/comparable evidence.
- [ ] Sources without a legitimate adapter remain labeled as planned/manual rather than falsely advertised as automated.

## 6. Final release gate

- [ ] GitHub Actions is green on `main`.
- [ ] Streamlit deployment starts without errors.
- [ ] Admin login works.
- [ ] Demo works.
- [ ] Holy Grail Finder opens and handles an empty/unconfigured source safely.
- [ ] Inventory/profit calculations work.
- [ ] No production credential is hardcoded in the repository.
- [ ] Rotate credentials again immediately if any secret is accidentally exposed.
