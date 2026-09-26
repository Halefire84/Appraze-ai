# Mobile POS: Stripe Connect architecture

Status as of 2026-09-26. Replaces the Android v5 design that stored each merchant's
Stripe **secret key** on the phone and called `api.stripe.com` directly.

## Rule

No Stripe secret key ever lives in a distributed app (Android, iOS, Windows). The only
Stripe secret is Appraze's **platform** key, held by the backend.

## Two money flows, kept separate

| Flow | Who pays whom | Where it lives |
|---|---|---|
| **POS** (this doc) | A merchant's customer pays the **merchant** | `pos_connect.py` + Android `PosScreen`/`PosApi` |
| **Appraze subscription** | A merchant pays **Appraze** | Play Billing (Android), `billing.py` (web). Untouched by this change. |

## Flow

```
Phone (device token only)          Appraze POS backend (platform key)       Stripe
------------------------           ---------------------------------       ------
Connect Stripe  ── POST /pos/connect/start ──►  create connected account ──► /v1/accounts
                                                create onboarding link  ──► /v1/account_links
            ◄── device_token + onboarding_url ─ store sha256(token)→acct
open onboarding_url in browser ───────────────────────────────────────────► Stripe-hosted KYC
Refresh    ── GET  /pos/connect/status ───────► retrieve account        ──► charges_enabled?
Charge     ── POST /pos/checkout ─────────────► Checkout Session ON the  ──► /v1/checkout/sessions
              {amount_cents, description,       merchant's account           (Stripe-Account: acct_…,
               invoice_id}                                                    Idempotency-Key)
            ◄── checkout_url ──────────────────
customer pays on Stripe's page ───────────────────────────────────────────► funds → merchant's bank
Check status ─ GET /pos/checkout/{id}/status ─► retrieve session on own acct
Disconnect ── POST /pos/disconnect ───────────► revoke token
```

Design choices:

- **Connected account type:** Standard-style, created through the v1 `controller` parameters.
  The merchant gets the full Stripe Dashboard, pays their own Stripe fees, and Stripe runs
  onboarding and KYC and carries negative-balance liability. Appraze never holds funds and
  takes no application fee.
- **Direct charges** (`Stripe-Account` header). The sale belongs to the merchant's account:
  their statement descriptor, their refunds, their disputes.
- **Checkout Session, not Payment Link.** A Payment Link can be paid many times; a Checkout
  Session is paid once.
- **Idempotency.** `invoice_id` maps to `Idempotency-Key = pos-checkout-{acct}-{invoice_id}`.
  The app reuses the invoice id while the amount and description are unchanged, so a retry
  after a timeout returns the same session. Reusing an id with different parameters returns
  409.
- **Device token.** The token is `apt_` followed by 256 random bits, and only
  `sha256(token)` is stored. The token is not a Stripe credential. It can only create or read
  Checkout Sessions that pay the merchant's own account, and Disconnect revokes it.
- **Legacy cleanup.** On launch the app deletes any `stripe_pk`/`stripe_sk` that a v5 build
  saved.

## Backend endpoints (`pos_connect.py`, mounted in `stripe_webhook_server.py`)

| Method | Path | Auth | Notes |
|---|---|---|---|
| POST | `/pos/connect/start` | none | 5/hour per IP, 200/day global |
| GET | `/pos/connect/status` | Bearer | `charges_enabled`, `details_submitted` |
| POST | `/pos/connect/link` | Bearer | fresh onboarding link |
| POST | `/pos/disconnect` | Bearer | revokes the token (does not touch the merchant's Stripe account) |
| POST | `/pos/checkout` | Bearer | amount must be an int in cents, $0.50 to `POS_MAX_AMOUNT_CENTS`; description 1–200 chars with control chars stripped; blocked until `charges_enabled` |
| GET | `/pos/checkout/{cs_…}/status` | Bearer | read only on the caller's own account |
| GET | `/pos/connect/return`, `/pos/connect/refresh`, `/pos/checkout/done`, `/pos/checkout/cancelled` | none | static landing pages |

Authed routes are limited to 60/min per token; checkout is limited to 30/min per account.
Stripe failures map to 4xx or 502, never 500. Keys and tokens are never logged.

## Environment

| Var | Meaning |
|---|---|
| `STRIPE_PLATFORM_SECRET_KEY` | Appraze platform key. A restricted key with Connect + Checkout write is preferred. |
| `POS_PUBLIC_BASE_URL` | `https://` URL of this service, used for Stripe return, refresh and success pages |
| `POS_CONNECT_DB` | SQLite path. **Must be on a persistent disk.** If it's lost, every device has to reconnect. |
| `POS_CONNECT_ALLOW_LIVE` | Must be `1` before a `sk_live_`/`rk_live_` key is accepted. Sandbox by default. |
| `POS_MAX_AMOUNT_CENTS` | Per-charge ceiling. Default `1000000` ($10,000). |

Android build: `gradle -PapprazePosApi=https://<host> :app:bundleRelease`. The app accepts
HTTPS only. Without the property, the POS tab shows "POS server not set up".

## Owner setup (needs Chris; nothing here spends money)

1. In the Stripe Dashboard, **test mode**, enable Connect and complete the platform profile.
2. Deploy `stripe_webhook_server.py` (it already hosts the webhook receiver) with the env
   vars above, a test-mode key and a persistent disk.
3. Build the app with `-PapprazePosApi=https://<host>`. On a device: Connect Stripe, run
   test-mode onboarding, then Charge $1.00 and pay with card `4242 4242 4242 4242`.
   Check Payment Status should read Paid.
4. Only after that proof: set `POS_CONNECT_ALLOW_LIVE=1` with a live key.

## Verification done in the 2026-09-26 session

- `tests/test_pos_connect.py`: 29 tests against a fake Stripe (auth, hashing, revocation,
  rate limits, validation, idempotent retry, cross-merchant isolation, error mapping, live-key
  guard).
- One contract test against **stripe-mock**, Stripe's official mock, which validates every
  request against Stripe's OpenAPI spec. The account create (with `controller`), the account
  link, the Checkout Session create (direct charge) and the session retrieve were all
  accepted. Run it with:
  `stripe-mock -http-port 12111 & STRIPE_MOCK_URL=http://localhost:12111 pytest tests/test_pos_connect.py`
- Android: `:app:assembleDebug`, `:app:bundleRelease`, `:app:lintDebug`, `:app:testDebugUnitTest` green.

**Not verified:** a real Stripe test-mode account, a real onboarding, and on-device UI. There was
no platform key and no emulator (no KVM) in this session.

## Known limitations / follow-ups

- The rate limiter is in-process, so it resets on restart and isn't shared across replicas.
  Use Redis or a gateway limit if the service is scaled out.
- `/pos/connect/start` is unauthenticated, apart from rate limits, because the app has no
  user accounts. Add Play Integrity / App Attest before a wide launch to stop scripted
  account creation.
- A device token is a bearer credential. Anyone who steals one can create checkout pages
  that pay the victim merchant, but cannot move money out. Revoke it with Disconnect.
- Android POS sales are not yet reconciled by webhook. The app polls Check Payment Status.
  A Connect webhook endpoint (`account`-scoped `checkout.session.completed`) feeding a
  per-merchant ledger is the next step. The existing `sales_log` is Appraze's own shared
  register and must not receive other merchants' sales.
- The Play **Data Safety** form must now declare that the POS sends the amount and
  description of each sale to the Appraze POS server, so it is not on-device only.
