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

## Tap to Pay on Android (added 2026-09-26)

The customer taps a contactless card or phone on the merchant's phone. This uses Stripe
Terminal SDK 5.8.1 (`stripeterminal-core` + `stripeterminal-taptopay`).

```
Phone                                   POS backend                     Stripe (merchant's account)
first time: business address ── POST /pos/terminal/location ──► /v1/terminal/locations
SDK needs a token ───────────── POST /pos/terminal/connection_token ─► /v1/terminal/connection_tokens
Tap to Pay button ───────────── POST /pos/terminal/payment_intent ──► /v1/payment_intents (card_present)
SDK: retrieve → collect (NFC tap) → confirm   ──────────────────────► charge
confirm result ──────────────── GET /pos/terminal/payment_intent/{pi}/status ─► re-read; only then PAID
```

- **Device requirements:** Android 11 or newer with NFC. Stripe also refuses rooted
  devices, developer-mode setups and debuggable apps for real taps. Debug builds therefore
  use Stripe's **simulated reader**, so real taps need a release build.
- **Location permission:** Stripe requires it for in-person payments, and the app asks the
  first time Tap to Pay is used.
- **minSdk:** raised from 23 to 26 because the Terminal SDK requires it. Android 8 and later
  still install the app; Tap to Pay just doesn't show on Android 8–10.
- **App size:** the release AAB grew from about 5 MB to about 36 MB because of Stripe's
  native Tap to Pay libraries.
- **SDK permissions** merged into the app: NFC, READ_PHONE_STATE, location, and Bluetooth
  (the Bluetooth ones are for Stripe's hardware readers and aren't used here). All of these
  must be declared on the Play Data Safety and permissions forms.

## Sales log (date and time)

Every POS sale, whether Tap to Pay or payment link, is logged on the device (`SalesLog`,
`sales.db`) with:
- the date and time it was started;
- the date and time it was confirmed paid (only after the server re-reads it from Stripe);
- method, amount, description, invoice id and Stripe id.

PAID is final, so a late failure or cancel can't overwrite it. The POS tab's **Recent Sales**
list shows entries such as "Sat, Sep 26, 2026 · 8:45 AM · Tap to Pay", and tapping a pending
row re-checks it. Server responses also carry `created_at` (Stripe's timestamp, ISO-8601
UTC) and `checked_at`. Stripe's Dashboard keeps its own permanent record of each payment.

## Backend endpoints (`pos_connect.py`, mounted in `stripe_webhook_server.py`)

| Method | Path | Auth | Notes |
|---|---|---|---|
| POST | `/pos/connect/start` | none | 5/hour per IP, 200/day global |
| GET | `/pos/connect/status` | Bearer | `charges_enabled`, `details_submitted` |
| POST | `/pos/connect/link` | Bearer | fresh onboarding link |
| POST | `/pos/disconnect` | Bearer | revokes the token (does not touch the merchant's Stripe account) |
| POST | `/pos/checkout` | Bearer | amount must be an int in cents, $0.50 to `POS_MAX_AMOUNT_CENTS`; description 1–200 chars with control chars stripped; blocked until `charges_enabled` |
| GET | `/pos/checkout/{cs_…}/status` | Bearer | read only on the caller's own account |
| GET/POST | `/pos/terminal/location` | Bearer | business address → one Terminal location per account |
| POST | `/pos/terminal/connection_token` | Bearer | requires location; 30/min per account |
| POST | `/pos/terminal/payment_intent` | Bearer | card_present, automatic capture; same validation and idempotency as checkout |
| GET | `/pos/terminal/payment_intent/{pi_…}/status` | Bearer | server-side truth for "paid" |
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
3. Build the app with `-PapprazePosApi=https://<host>`. For Tap to Pay, use a **release**
   build on an NFC phone running Android 11+ with developer options off, and test with a
   Stripe test card or a physical test card. On a device: Connect Stripe, run
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

Tap to Pay: 12 more backend tests, including the location, connection token and card_present
PaymentIntent request shapes accepted by stripe-mock. `SalesLogFormatTest` covers the
date/time formatting.

**Not verified:** a real NFC tap on a phone; a real Stripe test-mode account, a real onboarding, and on-device UI. There was
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
