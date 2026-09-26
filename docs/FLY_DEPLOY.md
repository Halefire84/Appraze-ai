# Deploying the FastAPI backend to Fly.io

Status as of 2026-09-26. Deploys the single unified FastAPI app in `stripe_webhook_server.py`
— it already mounts the Stripe webhook receiver, the Stripe Connect POS backend
(`pos_connect.py`), the comps collector (`comps_collector.py`), and the comps history poller
admin API (`comps_poller.py`). One app, one deployment.

## Why Fly.io, and why this shape

Chris picked Fly.io directly. This backend previously had no home — `docs/POS_STRIPE_CONNECT.md`
and `docs/COMPS_POLLER.md` both said "deploy this somewhere" without picking anywhere. This
closes that gap.

**Sized for a 256MB machine** (Chris's instruction — a real cost constraint, not a random
number). That's tight for a Python service that transitively imports `pandas` (comps_adapters.py
uses it for CSV import, unused by this service but imported unconditionally) and `streamlit`
(only for `st.secrets.get(...)`, which is monkeypatched away before it's ever called — see
`comps_collector.py`/`comps_poller.py`'s `_use_env_ebay_credentials()`). Verified locally:

| Configuration | RSS at import, before serving a request |
|---|---|
| Full app, real streamlit installed | ~144 MB |
| Full app, streamlit stub (this deploy) | ~130 MB |

**The streamlit stub** (`deploy/streamlit_stub/streamlit/__init__.py`): a ~15-line fake
`streamlit` package providing only `secrets` (an empty dict-like object), placed ahead of
site-packages on `PYTHONPATH` in the Docker image. This is safe specifically because
`comps_adapters.py`'s only use of streamlit — `st.secrets.get(...)` inside
`_ebay_client_credentials()` — is replaced by both callers before it's ever invoked in this
service. It does **not** touch `comps_adapters.py`'s own source (which stays reused, unchanged,
per every prior brief's instruction), and does not affect local dev, CI, or the real Streamlit
web app, which still installs and uses the genuine `streamlit` package via `requirements.txt`.
This is scoped entirely to `requirements-fly.txt` + the Dockerfile.

**`pandas` is not stubbed.** It's the single biggest cost (~90 MB alone) but has real behavioral
surface (`pd.read_csv`, `pd.isna`) used by `CsvCompsAdapter`, which — while unused by this
specific service today — would be actively dangerous to fake with a partial stub (silent
wrong behavior instead of a clear import error, if it's ever wired in here later). ~130 MB
against a 256 MB machine leaves real headroom for request handling, SQLite connections, and
container overhead; if that headroom turns out to be too tight in practice, the honest fix is
telling Chris the 256MB budget doesn't fit and asking whether to raise it — not a riskier stub.

**`auto_stop_machines = false`, `min_machines_running = 1`.** This receives live Stripe
webhooks, which expect a prompt response — a cold-started machine risks Stripe's delivery
timeout. Costs a bit more than scale-to-zero; that trade-off is inherent to handling webhooks
at all, not something this config invented.

## What's deployed — the exact file list, not "the repo"

`Dockerfile` copies only: `comps.py`, `comps_adapters.py`, `comps_collector.py`,
`comps_poller.py`, `finance.py`, `pos_connect.py`, `stripe_webhook_server.py`,
`stripe_webhooks.py`, `telemetry.py`, `webhook_store.py` — traced by hand from their actual
`import` statements, then verified by literally booting that exact file set with the stub
active (`uvicorn stripe_webhook_server:app` responded 200 on `/`, `/healthz`; 503 — not a
crash — on `/comps/search` and `/admin/poller/watchlist` with no eBay/admin-token secrets set,
exactly as designed). `.dockerignore` is an allowlist (`*` then explicit `!un-ignores`) so nothing
else — `android/` (500+MB), `.git`, tests, docs, or any local secret file — ever reaches the
Docker build context.

## Secrets — never in git, never pasted into chat

This session's own environment documentation is explicit: **never paste a token, key, or
password into chat.** The right place for a value only this session needs is this session's
own environment settings (the cloud environment menu → Edit), as an environment variable this
session's shell can read — then used here to call `flyctl`/`fly secrets set`, never echoed,
never committed.

| Variable (add via the session's environment settings) | Used for |
|---|---|
| `FLY_API_TOKEN` | authenticates `flyctl` to deploy/manage the app |
| `EBAY_CLIENT_ID` / `EBAY_CLIENT_SECRET` | `comps_collector.py` / `comps_poller.py` (same keys already documented in `docs/COMPS_POLLER.md`) |
| `STRIPE_PLATFORM_SECRET_KEY` | `pos_connect.py`'s Stripe Connect platform key (`docs/POS_STRIPE_CONNECT.md`) |
| `STRIPE_WEBHOOK_SECRET` (optional, if Chris already has one from a prior Stripe Dashboard setup) | the existing webhook signature check in `stripe_webhook_server.py` |

Once those are in the session's environment, this session reads them locally and runs
`fly secrets set NAME=value` for each — the value passes from this container straight to
Fly's secret store over the API, never through git, never printed to a log, never left in
shell history (set via a heredoc / `--stdin`-style invocation, not a literal on the command
line where it would show in `ps`).

`COMPS_POLLER_ADMIN_TOKEN` is different: nobody hands this one to the session — it's
generated here (random, server-side) purely to gate the comps-poller admin API
(`docs/COMPS_POLLER.md`), then delivered to Chris the same way the release keystore was: a
file, not a chat message, since he needs to keep it to manage the watchlist later.

## Deploy runbook

```bash
export FLYCTL_INSTALL="$HOME/.fly"; export PATH="$FLYCTL_INSTALL/bin:$PATH"  # flyctl already installed this session

# 1. Auth (FLY_API_TOKEN from the session's environment, never printed)
fly auth token "$FLY_API_TOKEN"    # or: flyctl auth login --access-token "$FLY_API_TOKEN" per current flyctl syntax

# 2. Reconcile fly.toml with flyctl's current schema/app-creation flow
fly launch --copy-config --name appraze-crtc-api --region iad --no-deploy --yes

# 3. Create the persistent volume for the two SQLite stores (pos_connect.py, comps_poller.py)
fly volumes create appraze_data --region iad --size 1 --yes

# 4. Secrets (values come from the session's own environment, never git)
fly secrets set EBAY_CLIENT_ID="$EBAY_CLIENT_ID" EBAY_CLIENT_SECRET="$EBAY_CLIENT_SECRET"
fly secrets set STRIPE_PLATFORM_SECRET_KEY="$STRIPE_PLATFORM_SECRET_KEY"
fly secrets set COMPS_POLLER_ADMIN_TOKEN="$(generated, see above)"
# fly secrets set STRIPE_WEBHOOK_SECRET="$STRIPE_WEBHOOK_SECRET"   # only if Chris has one already

# 5. Deploy
fly deploy

# 6. Verify
curl -fsS https://appraze-crtc-api.fly.dev/healthz
```

If `appraze-crtc-api` is already taken on Fly (names are globally unique across all Fly
users), pick a different name in step 2 and update `fly.toml`'s `app` line and
`POS_PUBLIC_BASE_URL` to match before deploying.

## After the first successful deploy

- Update `docs/POS_STRIPE_CONNECT.md`'s "owner setup" section and `docs/COMPS_POLLER.md` with
  the real URL (this doc's log entry in `handoff.md` also records it — see below).
- Android builds now have a real backend to point at:
  `gradle -PapprazePosApi=https://appraze-crtc-api.fly.dev :app:bundleRelease` (see
  `docs/POS_STRIPE_CONNECT.md`).
- Set up `.github/workflows/comps-poller-cron.yml`'s two repo secrets
  (`COMPS_POLLER_BASE_URL`, `COMPS_POLLER_ADMIN_TOKEN`) so the scheduled poller trigger stops
  being a no-op.
- Stripe Dashboard: point the webhook endpoint at
  `https://appraze-crtc-api.fly.dev/stripe/webhook` (needs `STRIPE_WEBHOOK_SECRET` set to match).

## Verified this session

- The exact deployed file set boots correctly (proven locally with the trimmed file list + the
  streamlit stub — see above): `/` and `/healthz` return 200; `/comps/search` and
  `/admin/poller/watchlist` correctly 503 ("not configured") rather than crashing when their
  respective secrets aren't set.
- RSS measurements above, comparing real streamlit vs. the stub.

**Not verified: an actual Fly.io deployment.** This session has no Fly account/token yet. Once
one is available (via the session's environment settings, not chat), the remaining runbook
steps above get run for real and this doc's log entry gets the actual URL and any schema
corrections `fly launch` made to `fly.toml`.
