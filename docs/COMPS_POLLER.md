# Comps history poller

Status as of 2026-09-26. Brief: `briefs/comps-collector-brief-2026-09-26.md` (in the
`appraze-plans` repo) — its "Build" section, items 1-4. Additive only: `comps.py` and
`comps_adapters.py` are unchanged.

## What this answers, and what it doesn't

`comps_collector.py` (shipped earlier) answers "what's this worth right now?" with one live
eBay Browse API call. This module (`comps_poller.py`) answers a different question: it polls
a **watchlist** of queries on a schedule, on a budget, and keeps a local history — so a later
lookup has more evidence than a single snapshot, and so the app can show a price trend, not
just a point value.

## The honesty line (read this before changing the inference logic)

The brief asks for **sold-inference**: an item that was showing up in search results and
then stops is *probably* sold. That's a real, useful signal — but eBay's Browse API search
is relevance-ranked, not an exhaustive/stable feed. An item can also vanish from a poll's
top-50 results because it fell in ranking, the seller re-listed it under a new item id, or it
expired unsold. There is no way to tell these apart from the Browse API alone.

`comps.py`'s own confidence math treats `listing_type == SOLD` as real transaction evidence
and rates it higher-confidence than an asking price. Feeding an inferred disappearance into
that pipeline as `SOLD` would quietly lie to it — the same principle
`EbayMarketplaceInsightsAdapter`'s own docstring states ("never fabricates sold data").

**So this module never does that.** `PollerCompsAdapter.fetch_comps()` — the thing that
feeds comps.py — only ever returns `listing_type=comps.ACTIVE`, drawn from a bigger,
longer-observed sample of real active listings than one live call gives you. The
sold-inference signal is exposed *separately*, clearly labeled, through
`price_trend()` / `recent_inferred_sales()` / the `/admin/poller/trend` endpoint's
`inferred_sold_count` — for a human (or a future, explicitly-approved change) to decide how
much to trust and where else to use it. **This is a real design choice, not an oversight.**
If you want inferred-sold data to actually feed the BUY/PASS math, that's a decision for
Chris, made explicitly, not something to quietly wire in here.

To reduce noise, an item only counts as "inferred sold" once it's been seen at least
`MIN_SIGHTINGS_FOR_SOLD_INFERENCE` (2) times before it vanishes — a single sighting then gone
is too easily just search-ranking churn.

## Scope: why this doesn't scrape anything

The brief frames official-API-only vs. a scraper supplement as Chris's open call, but its own
"Build" section is unconditional and scoped entirely to the Browse API — an approved,
ToS-compliant integration already used elsewhere in this app. This module implements exactly
that scope and nothing else. It does not scrape eBay, and does not implement the brief's
option (b) (scraper supplement) or (c) (paid harvester) — those stay open, budget/approval-
gated decisions for Chris. See the brief itself for the full trade-off writeup.

## What's here

- **`PollerStore`** (SQLite, default `comps_poller.sqlite3`, path via `COMPS_POLLER_DB`):
  a watchlist, per-item snapshot state (`listing_snapshots`), a full price history
  (`price_observations`, for the trend rollups), and a poll-run log (`poll_runs`).
- **`ComPoller`**: polls due watches (respecting `COMPS_POLLER_INTERVAL_MINUTES`, default
  240 = 4h, so the same watch isn't re-polled too often) against
  `comps_adapters.EbayBrowseAdapter.fetch_listings` (one Browse search page, ≤50 results,
  active listings only), on a **daily call budget**.
- **Rate budget**: `COMPS_POLLER_DAILY_CALL_BUDGET`, default a deliberately conservative 300.
  eBay's actual Browse API entitlement varies by app/tier and this code makes no claim about
  it — confirm your entitlement in the eBay Developer dashboard and raise the env var there,
  not by assuming a number. A poll run that hits the budget stops cleanly
  (`budget_exhausted=True` in the result), not an error, and resumes on the next scheduled run.
- **`PollerCompsAdapter`**: an ordinary `comps_adapters`-style adapter
  (`fetch_comps(query, limit)`) over the accumulated *still-active* history — a bigger,
  honestly-labeled ACTIVE sample for `comps.summarize_comps()`.
- **`price_trend()`**: recent-vs-prior median comparison (default: last 30 days vs. the 30
  days before that) plus the inferred-sold count — a supplementary signal, not `comps.py`'s
  confidence math.
- **Admin HTTP API** (mounted on the existing FastAPI service, `stripe_webhook_server.py`),
  protected by `COMPS_POLLER_ADMIN_TOKEN` (a bearer token; unset = every admin route 503s):

| Method | Path | Purpose |
|---|---|---|
| POST | `/admin/poller/watchlist` | add a watch (`{"query": "...", "category_id": "..."}`) |
| GET | `/admin/poller/watchlist` | list watches |
| DELETE | `/admin/poller/watchlist/{id}` | remove a watch |
| POST | `/admin/poller/watchlist/{id}/enabled` | pause/resume (`{"enabled": false}`) |
| POST | `/admin/poller/run?force_all=1` | poll due watches now (or all, with `force_all`) |
| GET | `/admin/poller/status` | recent poll runs, watch counts |
| GET | `/admin/poller/trend?query=...` | price trend for one query |

- **CLI** (for a cron job on the same host/DB, no HTTP hop needed):
  ```bash
  python3 -m comps_poller add "Pyrex 403 mixing bowl"
  python3 -m comps_poller list
  python3 -m comps_poller run [--force-all]
  ```
- **Scheduled trigger**: `.github/workflows/comps-poller-cron.yml` hits
  `POST /admin/poller/run` every 4 hours via `COMPS_POLLER_BASE_URL` /
  `COMPS_POLLER_ADMIN_TOKEN` repo secrets. Without those secrets set, every run is a clean,
  green no-op — it never fails CI. Use this when the poller runs on a different host than
  wherever cron would otherwise live; use the CLI directly if it's the same host.

## A known, documented limitation

`normalize_title()` (used for "median by normalized title" rollups) is deliberately simple:
lowercase, strip punctuation, collapse whitespace. It groups near-identical titles (case,
punctuation, extra spaces) — it does **not** understand synonyms, size variants, or that two
differently-worded listings are "the same item." That's an intentional, documented scope
limit, not a bug: solving real product/title matching is a separate, much bigger project.

## Item 4 of the brief: Marketplace Insights application

A business-justification draft for the eBay Marketplace Insights (Limited Release, real sold
prices) application is at `docs/EBAY_MARKETPLACE_INSIGHTS_APPLICATION.md`. Per the brief,
Chris submits this himself — no code change unlocks this API; it's an eBay approval process.

## Verified this session

- `tests/test_comps_poller.py`: 40 tests (fake eBay, no network) covering the watchlist,
  snapshot/disappearance/sold-inference logic (including the honesty rule end-to-end through
  `comps.summarize_comps`), budget exhaustion, error handling, the HTTP admin API, and the CLI.
- Full suite: 627 passed, 2 skipped (pre-existing stripe-mock contract tests that skip
  without `STRIPE_MOCK_URL`, unrelated to this module).
- `flake8`, `compileall` clean.

**Not verified:** a real eBay Browse API call (needs `EBAY_CLIENT_ID`/`EBAY_CLIENT_SECRET` on
the deployed server — same credentials `comps_collector.py` already uses), and the scheduled
GitHub Actions trigger actually reaching a deployed instance (needs the two repo secrets set).

## Environment

| Var | Meaning | Default |
|---|---|---|
| `EBAY_CLIENT_ID` / `EBAY_CLIENT_SECRET` | same eBay app keys `comps_collector.py` uses | — |
| `COMPS_POLLER_ADMIN_TOKEN` | bearer token for the admin API; unset = admin routes 503 | unset |
| `COMPS_POLLER_DB` | SQLite path | `comps_poller.sqlite3` |
| `COMPS_POLLER_DAILY_CALL_BUDGET` | hard ceiling on this poller's own Browse API calls/day | 300 |
| `COMPS_POLLER_INTERVAL_MINUTES` | minimum minutes between polls of the same watch | 240 |
