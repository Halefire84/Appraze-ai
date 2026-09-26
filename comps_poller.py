"""
comps_poller.py — background eBay Browse-API history poller.

Brief: briefs/comps-collector-brief-2026-09-26.md ("Build" section). Additive
only: does not touch comps.py or comps_adapters.py, both reused unchanged.

WHAT THIS IS
------------
comps_collector.py (the on-demand lookup, shipped earlier) answers "what's
this worth right now?" with a single live Browse API call. This module
answers a different question: it polls a watchlist of queries over time,
on a budget, and builds a local history of active-listing prices per item so
later lookups have more evidence than one snapshot, and so the app can show
a price trend, not just a point value.

THE SOLD-INFERENCE HONESTY LINE (read before changing anything below)
-----------------------------------------------------------------------
The brief asks for "sold-inference": an item that was showing up in search
results and then stops is *probably* sold. That is a real, useful signal,
but it is not proof — eBay's Browse API search is relevance-ranked, not an
exhaustive/stable listing feed, so an item can also vanish from a poll's
top-N results because it fell in ranking, the seller edited it (new item
id), or it expired unsold. comps.py's own confidence math treats
listing_type == SOLD as real transaction evidence and rates it accordingly
higher-confidence than an asking price (see comps.py's _rate_confidence).
Feeding inferred disappearances into comps.py as SOLD would quietly lie to
that confidence math — comps.py's other adapters go out of their way not to
fake sold data (see EbayMarketplaceInsightsAdapter's docstring), and this
module follows the same rule:

    Inferred disappearances are NEVER returned to comps.py as SOLD comps.

PollerCompsAdapter.fetch_comps() below only ever returns
listing_type=comps.ACTIVE. The inferred-sold signal is exposed separately,
clearly labeled "inferred", through price_trend() / recent_inferred_sales(),
for a caller (or Chris) to decide how much to trust and where else to use it.
This is a real design choice, not an oversight — flagged prominently in
docs/COMPS_POLLER.md for the same reason.

SCOPE (per the brief's own resolution — do not re-litigate scraping here)
--------------------------------------------------------------------------
The brief presents official-API-only vs. a scraper supplement as Chris's
open decision, but its own "Build" section is unconditional and scoped
entirely to the Browse API (an approved, ToS-compliant, keys-server-side
integration already used elsewhere in this app). This module implements
exactly that scope. It does not scrape eBay in any form, and does not
implement the brief's option (b)/(c) (scraper supplement, paid harvester) —
those remain open, budget/approval-gated decisions for Chris, discussed in
docs/COMPS_POLLER.md, not built here.

RATE BUDGET
-----------
eBay's exact Browse API entitlement varies by app/tier and can change; this
module does not assume a specific number. COMPS_POLLER_DAILY_CALL_BUDGET
(env var) sets a hard daily ceiling on this poller's own Browse API calls,
defaulting to a deliberately conservative 300/day — confirm your actual
entitlement in the eBay Developer dashboard and raise it there, not by
assuming eBay's default. A poll run stops (not crashes) once the budget is
spent for the day and resumes on the next scheduled run.
"""

from __future__ import annotations

import logging
import os
import re
import secrets
import sqlite3
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import requests
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

import comps
import comps_adapters
from pos_connect import RateLimiter

logger = logging.getLogger("comps_poller")

DEFAULT_DB_PATH = "comps_poller.sqlite3"
DEFAULT_DAILY_CALL_BUDGET = 300
DEFAULT_POLL_INTERVAL_MINUTES = 240  # don't re-poll the same watch more than once per 4h
MIN_SIGHTINGS_FOR_SOLD_INFERENCE = 2  # a single sighting then gone is too noisy to call "sold"
MAX_QUERY_LEN = 100
MAX_LISTINGS_PER_POLL = 50  # one Browse search page; see docs/COMPS_POLLER.md on why not more
STALE_ACTIVE_DAYS = 45  # an item not re-seen this long is dropped from "still active" bookkeeping

_CONTROL_CHARS_RE = re.compile(r"[\x00-\x1f\x7f]")
_NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")


class PollerError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status
        self.message = message


def _use_env_ebay_credentials() -> None:
    """comps_adapters reads eBay keys from Streamlit secrets, which don't
    exist in this FastAPI service; same fix as comps_collector.py, applied
    idempotently so either module can call it in any order."""
    from comps_collector import _env_ebay_credentials
    comps_adapters._ebay_client_credentials = _env_ebay_credentials


def normalize_title(title: str) -> str:
    """Lowercase, punctuation-stripped, whitespace-collapsed grouping key
    for "median by normalized title" rollups. Deliberately simple (no
    stemming/synonyms) — it groups near-identical titles (case, punctuation,
    extra spaces), not different listings of "the same" item worded
    differently; see docs/COMPS_POLLER.md for why that's an intentional,
    documented limitation rather than a bug."""
    return _NON_ALNUM_RE.sub(" ", (title or "").lower()).strip()


def validate_query(value: Any) -> str:
    if not isinstance(value, str):
        raise PollerError(400, "query must be text.")
    q = " ".join(_CONTROL_CHARS_RE.sub(" ", value).split())
    if len(q) < 2:
        raise PollerError(400, "query is too short.")
    if len(q) > MAX_QUERY_LEN:
        raise PollerError(400, f"query is over {MAX_QUERY_LEN} characters.")
    return q


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: datetime) -> str:
    return dt.isoformat()


def parse_iso(s: Optional[str]) -> Optional[datetime]:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s)
    except ValueError:
        return None


@dataclass
class WatchRow:
    id: int
    query: str
    category_id: str
    enabled: bool
    created_at: str
    last_polled_at: Optional[str]


@dataclass
class PollRunResult:
    watch_id: int
    query: str
    calls_made: int
    seen: int
    new_items: int
    disappeared_items: int
    inferred_sold: int
    budget_exhausted: bool
    error: Optional[str] = None


class PollerStore:
    """SQLite store for the watchlist, per-item snapshot state, price
    history, and a poll-run log. One connection per call (matches
    pos_connect.TokenStore's pattern) so it's safe under a threaded ASGI
    server; writes are additionally serialized with a lock."""

    def __init__(self, path: Optional[str] = None):
        self.path = path or os.environ.get("COMPS_POLLER_DB", DEFAULT_DB_PATH)
        self._lock = threading.Lock()
        with self._conn() as c:
            c.execute(
                "CREATE TABLE IF NOT EXISTS watchlist ("
                " id INTEGER PRIMARY KEY AUTOINCREMENT,"
                " query TEXT NOT NULL,"
                " category_id TEXT NOT NULL DEFAULT '',"
                " enabled INTEGER NOT NULL DEFAULT 1,"
                " created_at TEXT NOT NULL,"
                " last_polled_at TEXT)"
            )
            c.execute(
                "CREATE TABLE IF NOT EXISTS listing_snapshots ("
                " source_listing_id TEXT PRIMARY KEY,"
                " watch_id INTEGER NOT NULL,"
                " query TEXT NOT NULL,"
                " title TEXT NOT NULL DEFAULT '',"
                " normalized_title TEXT NOT NULL DEFAULT '',"
                " category TEXT NOT NULL DEFAULT '',"
                " price REAL NOT NULL,"
                " shipping REAL NOT NULL DEFAULT 0,"
                " condition TEXT NOT NULL DEFAULT '',"
                " url TEXT NOT NULL DEFAULT '',"
                " first_seen TEXT NOT NULL,"
                " last_seen TEXT NOT NULL,"
                " times_seen INTEGER NOT NULL DEFAULT 1,"
                " still_active INTEGER NOT NULL DEFAULT 1,"
                " disappeared_at TEXT,"
                " inferred_sold INTEGER NOT NULL DEFAULT 0)"
            )
            c.execute("CREATE INDEX IF NOT EXISTS idx_snap_query ON listing_snapshots(query)")
            c.execute("CREATE INDEX IF NOT EXISTS idx_snap_norm_title ON listing_snapshots(normalized_title)")
            c.execute(
                "CREATE TABLE IF NOT EXISTS price_observations ("
                " id INTEGER PRIMARY KEY AUTOINCREMENT,"
                " source_listing_id TEXT NOT NULL,"
                " query TEXT NOT NULL,"
                " normalized_title TEXT NOT NULL DEFAULT '',"
                " price REAL NOT NULL,"
                " shipping REAL NOT NULL DEFAULT 0,"
                " observed_at TEXT NOT NULL)"
            )
            c.execute("CREATE INDEX IF NOT EXISTS idx_obs_query_time ON price_observations(query, observed_at)")
            c.execute(
                "CREATE INDEX IF NOT EXISTS idx_obs_norm_time ON price_observations(normalized_title, observed_at)"
            )
            c.execute(
                "CREATE TABLE IF NOT EXISTS poll_runs ("
                " id INTEGER PRIMARY KEY AUTOINCREMENT,"
                " watch_id INTEGER NOT NULL,"
                " query TEXT NOT NULL,"
                " started_at TEXT NOT NULL,"
                " finished_at TEXT,"
                " calls_made INTEGER NOT NULL DEFAULT 0,"
                " seen INTEGER NOT NULL DEFAULT 0,"
                " new_items INTEGER NOT NULL DEFAULT 0,"
                " disappeared_items INTEGER NOT NULL DEFAULT 0,"
                " inferred_sold INTEGER NOT NULL DEFAULT 0,"
                " error TEXT)"
            )

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=10)
        conn.row_factory = sqlite3.Row
        return conn

    # ---- watchlist ----

    def add_watch(self, query: str, category_id: str = "") -> int:
        now = iso(utc_now())
        with self._lock, self._conn() as c:
            cur = c.execute(
                "INSERT INTO watchlist (query, category_id, enabled, created_at) VALUES (?, ?, 1, ?)",
                (query, category_id, now),
            )
            return cur.lastrowid

    def list_watches(self, enabled_only: bool = False) -> List[WatchRow]:
        sql = "SELECT * FROM watchlist"
        if enabled_only:
            sql += " WHERE enabled = 1"
        sql += " ORDER BY id"
        with self._conn() as c:
            rows = c.execute(sql).fetchall()
        return [WatchRow(r["id"], r["query"], r["category_id"], bool(r["enabled"]),
                         r["created_at"], r["last_polled_at"]) for r in rows]

    def get_watch(self, watch_id: int) -> Optional[WatchRow]:
        with self._conn() as c:
            r = c.execute("SELECT * FROM watchlist WHERE id = ?", (watch_id,)).fetchone()
        if not r:
            return None
        return WatchRow(r["id"], r["query"], r["category_id"], bool(r["enabled"]),
                        r["created_at"], r["last_polled_at"])

    def set_enabled(self, watch_id: int, enabled: bool) -> bool:
        with self._lock, self._conn() as c:
            cur = c.execute("UPDATE watchlist SET enabled = ? WHERE id = ?", (1 if enabled else 0, watch_id))
        return cur.rowcount > 0

    def delete_watch(self, watch_id: int) -> bool:
        with self._lock, self._conn() as c:
            cur = c.execute("DELETE FROM watchlist WHERE id = ?", (watch_id,))
        return cur.rowcount > 0

    def touch_watch_polled(self, watch_id: int, when: datetime) -> None:
        with self._lock, self._conn() as c:
            c.execute("UPDATE watchlist SET last_polled_at = ? WHERE id = ?", (iso(when), watch_id))

    def due_watches(self, interval_minutes: int) -> List[WatchRow]:
        cutoff = utc_now()
        out = []
        for w in self.list_watches(enabled_only=True):
            last = parse_iso(w.last_polled_at)
            if last is None or (cutoff - last).total_seconds() >= interval_minutes * 60:
                out.append(w)
        return out

    # ---- snapshots ----

    def get_snapshot(self, source_listing_id: str) -> Optional[sqlite3.Row]:
        with self._conn() as c:
            return c.execute("SELECT * FROM listing_snapshots WHERE source_listing_id = ?",
                             (source_listing_id,)).fetchone()

    def upsert_seen(self, watch: WatchRow, listing: Dict[str, Any], when: datetime) -> bool:
        """Records one still-seen listing. Returns True if this is a new item."""
        sid = listing["source_listing_id"]
        norm = normalize_title(listing.get("title", ""))
        existing = self.get_snapshot(sid)
        with self._lock, self._conn() as c:
            if existing is None:
                c.execute(
                    "INSERT INTO listing_snapshots (source_listing_id, watch_id, query, title, "
                    " normalized_title, category, price, shipping, condition, url, first_seen, "
                    " last_seen, times_seen, still_active, disappeared_at, inferred_sold)"
                    " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, 1, NULL, 0)",
                    (sid, watch.id, watch.query, listing.get("title", ""), norm,
                     listing.get("category", ""), listing["price"], listing.get("shipping", 0.0),
                     listing.get("condition", ""), listing.get("url", ""), iso(when), iso(when)),
                )
                is_new = True
            else:
                c.execute(
                    "UPDATE listing_snapshots SET price = ?, shipping = ?, condition = ?, "
                    " last_seen = ?, times_seen = times_seen + 1, still_active = 1, "
                    " disappeared_at = NULL, inferred_sold = 0 WHERE source_listing_id = ?",
                    (listing["price"], listing.get("shipping", 0.0), listing.get("condition", ""),
                     iso(when), sid),
                )
                is_new = False
            c.execute(
                "INSERT INTO price_observations (source_listing_id, query, normalized_title, price, "
                " shipping, observed_at) VALUES (?, ?, ?, ?, ?, ?)",
                (sid, watch.query, norm, listing["price"], listing.get("shipping", 0.0), iso(when)),
            )
        return is_new

    def mark_disappeared(self, watch_id: int, seen_ids: set, when: datetime) -> Tuple[int, int]:
        """Marks previously-active items from this watch that were not in
        this poll's results as gone. Returns (disappeared_count, inferred_sold_count)."""
        with self._conn() as c:
            rows = c.execute(
                "SELECT source_listing_id, times_seen FROM listing_snapshots"
                " WHERE watch_id = ? AND still_active = 1", (watch_id,),
            ).fetchall()
        gone = [r for r in rows if r["source_listing_id"] not in seen_ids]
        if not gone:
            return 0, 0
        inferred = 0
        with self._lock, self._conn() as c:
            for r in gone:
                is_inferred = r["times_seen"] >= MIN_SIGHTINGS_FOR_SOLD_INFERENCE
                if is_inferred:
                    inferred += 1
                c.execute(
                    "UPDATE listing_snapshots SET still_active = 0, disappeared_at = ?, "
                    " inferred_sold = ? WHERE source_listing_id = ?",
                    (iso(when), 1 if is_inferred else 0, r["source_listing_id"]),
                )
        return len(gone), inferred

    def prune_stale(self, older_than_days: int = STALE_ACTIVE_DAYS) -> int:
        """Drops bookkeeping for items not re-seen in a long time so a
        permanently-removed listing doesn't sit "still_active" forever
        after this poller simply stops being asked about its query."""
        cutoff = iso(utc_now())
        with self._lock, self._conn() as c:
            cur = c.execute(
                "DELETE FROM listing_snapshots WHERE still_active = 1 AND "
                " julianday(?) - julianday(last_seen) > ?",
                (cutoff, older_than_days),
            )
        return cur.rowcount

    # ---- reads for the comps adapter / rollups ----

    def active_snapshots_for_query(self, query: str, within_days: int = 30, limit: int = 50) -> List[sqlite3.Row]:
        cutoff = iso(utc_now())
        with self._conn() as c:
            return c.execute(
                "SELECT * FROM listing_snapshots WHERE query = ? AND still_active = 1"
                " AND julianday(?) - julianday(first_seen) <= ?"
                " ORDER BY last_seen DESC LIMIT ?",
                (query, cutoff, within_days, limit),
            ).fetchall()

    def price_history(self, query: str = "", normalized_title: str = "", days: int = 60) -> List[sqlite3.Row]:
        cutoff = iso(utc_now())
        if normalized_title:
            sql = ("SELECT * FROM price_observations WHERE normalized_title = ? AND"
                   " julianday(?) - julianday(observed_at) <= ? ORDER BY observed_at")
            args = (normalized_title, cutoff, days)
        else:
            sql = ("SELECT * FROM price_observations WHERE query = ? AND"
                   " julianday(?) - julianday(observed_at) <= ? ORDER BY observed_at")
            args = (query, cutoff, days)
        with self._conn() as c:
            return c.execute(sql, args).fetchall()

    def recent_inferred_sales(self, query: str = "", limit: int = 20) -> List[sqlite3.Row]:
        sql = "SELECT * FROM listing_snapshots WHERE inferred_sold = 1"
        args: Tuple[Any, ...] = ()
        if query:
            sql += " AND query = ?"
            args = (query,)
        sql += " ORDER BY disappeared_at DESC LIMIT ?"
        with self._conn() as c:
            return c.execute(sql, args + (limit,)).fetchall()

    def record_run(self, r: PollRunResult, started_at: datetime, finished_at: datetime) -> None:
        with self._lock, self._conn() as c:
            c.execute(
                "INSERT INTO poll_runs (watch_id, query, started_at, finished_at, calls_made, seen,"
                " new_items, disappeared_items, inferred_sold, error) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (r.watch_id, r.query, iso(started_at), iso(finished_at), r.calls_made, r.seen,
                 r.new_items, r.disappeared_items, r.inferred_sold, r.error),
            )

    def recent_runs(self, limit: int = 20) -> List[sqlite3.Row]:
        with self._conn() as c:
            return c.execute("SELECT * FROM poll_runs ORDER BY id DESC LIMIT ?", (limit,)).fetchall()


class ComPoller:
    """Polls due watches against eBay Browse API active listings, on a
    daily call budget, and records what it sees for later rollups."""

    def __init__(self, store: Optional[PollerStore] = None,
                 adapter: Optional[comps_adapters.EbayBrowseAdapter] = None,
                 limiter: Optional[RateLimiter] = None,
                 daily_budget: Optional[int] = None,
                 poll_interval_minutes: Optional[int] = None,
                 clock=time.time):
        self.store = store or PollerStore()
        self.adapter = adapter or comps_adapters.EbayBrowseAdapter()
        self.limiter = limiter or RateLimiter(clock=lambda: clock())
        self.daily_budget = daily_budget if daily_budget is not None else int(
            os.environ.get("COMPS_POLLER_DAILY_CALL_BUDGET", DEFAULT_DAILY_CALL_BUDGET))
        self.poll_interval_minutes = poll_interval_minutes if poll_interval_minutes is not None else int(
            os.environ.get("COMPS_POLLER_INTERVAL_MINUTES", DEFAULT_POLL_INTERVAL_MINUTES))
        self._clock = clock

    def _budget_left(self) -> bool:
        return self.limiter.allow("poller_daily_calls", "global", self.daily_budget, 86400.0)

    def poll_watch(self, watch: WatchRow) -> PollRunResult:
        started = utc_now()
        calls = 0
        error = None
        seen_ids: set = set()
        new_items = 0
        try:
            if not self._budget_left():
                return self._finish(watch, started, calls=0, seen_ids=seen_ids, new_items=0,
                                    budget_exhausted=True)
            listings = self.adapter.fetch_listings(watch.query, limit=MAX_LISTINGS_PER_POLL)
            calls += 1
            for listing in listings:
                sid = listing.get("source_listing_id") or ""
                if not sid:
                    continue
                seen_ids.add(sid)
                if self.store.upsert_seen(watch, listing, started):
                    new_items += 1
        except comps_adapters.EbayAuthError as e:
            error = f"eBay not configured: {e}"
        except requests.RequestException as e:
            error = f"eBay request failed: {type(e).__name__}"
        return self._finish(watch, started, calls=calls, seen_ids=seen_ids, new_items=new_items,
                            error=error)

    def _finish(self, watch: WatchRow, started: datetime, *, calls: int, seen_ids: set,
                new_items: int, error: Optional[str] = None, budget_exhausted: bool = False) -> PollRunResult:
        disappeared = inferred = 0
        if not error and not budget_exhausted:
            disappeared, inferred = self.store.mark_disappeared(watch.id, seen_ids, started)
        self.store.touch_watch_polled(watch.id, started)
        result = PollRunResult(
            watch_id=watch.id, query=watch.query, calls_made=calls, seen=len(seen_ids),
            new_items=new_items, disappeared_items=disappeared, inferred_sold=inferred,
            budget_exhausted=budget_exhausted, error=error,
        )
        self.store.record_run(result, started, utc_now())
        if error:
            logger.warning("Poll failed for watch %s (%s): %s", watch.id, watch.query, error)
        else:
            logger.info("Polled watch %s (%s): seen=%s new=%s disappeared=%s inferred_sold=%s",
                        watch.id, watch.query, len(seen_ids), new_items, disappeared, inferred)
        return result

    def run_due(self, force_all: bool = False) -> List[PollRunResult]:
        """poll_watch() itself checks the daily budget before spending a
        call, and records a budget_exhausted result (not an error) once
        it's spent — so this just keeps calling it for every due watch and
        lets that per-watch check do the work; no separate pre-check here."""
        watches = self.store.list_watches(enabled_only=True) if force_all else \
            self.store.due_watches(self.poll_interval_minutes)
        return [self.poll_watch(w) for w in watches]


class PollerCompsAdapter:
    """Feeds the poller's accumulated ACTIVE-listing history into comps.py
    as an ordinary comps_adapters-style adapter (fetch_comps(query, limit)).
    Every Comp returned is listing_type=comps.ACTIVE — see the module
    docstring for why inferred-sold rows are deliberately never surfaced
    here. A caller with more history than a single live Browse call gets a
    bigger, still-honestly-labeled active-listings sample."""

    def __init__(self, store: Optional[PollerStore] = None, within_days: int = 30):
        self.store = store or PollerStore()
        self.within_days = within_days

    def fetch_comps(self, query: str, limit: int = 20) -> List[comps.Comp]:
        rows = self.store.active_snapshots_for_query(query, within_days=self.within_days, limit=limit)
        return [
            comps.Comp(
                price=r["price"], source="eBay (poller history)", listing_type=comps.ACTIVE,
                condition=r["condition"] or "", shipping=r["shipping"] or 0.0,
                listing_date=r["first_seen"], title=r["title"] or "", url=r["url"] or "",
            )
            for r in rows
        ]


@dataclass
class PriceTrend:
    query: str
    sample_count: int
    recent_median: Optional[float]
    prior_median: Optional[float]
    trend_pct: Optional[float]  # (recent - prior) / prior * 100; None if not computable
    inferred_sold_count: int
    window_days: int


def _median(values: List[float]) -> Optional[float]:
    if not values:
        return None
    s = sorted(values)
    n = len(s)
    mid = n // 2
    return s[mid] if n % 2 else (s[mid - 1] + s[mid]) / 2.0


def price_trend(store: PollerStore, query: str, *, window_days: int = 60, split_days: int = 30) -> PriceTrend:
    """Splits the observation window in half and compares medians, e.g. 'the
    last 30 days vs. the 30 days before that.' This is NOT comps.py's
    confidence math (that needs a single point value); it's a supplementary
    signal for showing "prices trending up/down" alongside a comps result."""
    rows = store.price_history(query=query, days=window_days)
    now = utc_now()
    recent, prior = [], []
    for r in rows:
        observed = parse_iso(r["observed_at"])
        if observed is None:
            continue
        age_days = (now - observed).total_seconds() / 86400.0
        total = r["price"] + (r["shipping"] or 0.0)
        (recent if age_days <= split_days else prior).append(total)
    recent_med = _median(recent)
    prior_med = _median(prior)
    trend_pct = None
    if recent_med is not None and prior_med:
        trend_pct = round((recent_med - prior_med) / prior_med * 100, 1)
    inferred = len(store.recent_inferred_sales(query=query, limit=10_000))
    return PriceTrend(
        query=query, sample_count=len(rows), recent_median=recent_med, prior_median=prior_med,
        trend_pct=trend_pct, inferred_sold_count=inferred, window_days=window_days,
    )


# --------------------------------------------------------------------------
# HTTP layer (admin-only: these spend eBay call budget / change the
# watchlist, so they are not open like /comps/search)
# --------------------------------------------------------------------------

router = APIRouter()

_poller: Optional["ComPoller"] = None
_poller_lock = threading.Lock()


def get_poller() -> "ComPoller":
    global _poller
    with _poller_lock:
        if _poller is None:
            _use_env_ebay_credentials()
            _poller = ComPoller()
        return _poller


def set_poller(poller: Optional["ComPoller"]) -> None:
    """Test hook."""
    global _poller
    with _poller_lock:
        _poller = poller


def _admin_token_configured() -> str:
    return os.environ.get("COMPS_POLLER_ADMIN_TOKEN", "").strip()


def _check_admin(request: Request) -> None:
    configured = _admin_token_configured()
    if not configured:
        raise PollerError(503, "Poller admin endpoints are not configured on this server.")
    auth = request.headers.get("authorization", "")
    given = auth[7:].strip() if auth.lower().startswith("bearer ") else ""
    if not given or not secrets.compare_digest(given, configured):
        raise PollerError(401, "Invalid or missing admin token.")


def _err(e: PollerError) -> JSONResponse:
    return JSONResponse(status_code=e.status, content={"ok": False, "error": e.message})


def _watch_json(w: WatchRow) -> Dict[str, Any]:
    return {"id": w.id, "query": w.query, "category_id": w.category_id, "enabled": w.enabled,
            "created_at": w.created_at, "last_polled_at": w.last_polled_at}


def _run_json(r: PollRunResult) -> Dict[str, Any]:
    return {"watch_id": r.watch_id, "query": r.query, "calls_made": r.calls_made, "seen": r.seen,
            "new_items": r.new_items, "disappeared_items": r.disappeared_items,
            "inferred_sold": r.inferred_sold, "budget_exhausted": r.budget_exhausted, "error": r.error}


@router.post("/admin/poller/watchlist")
async def add_watch(request: Request):
    try:
        _check_admin(request)
        body = await request.json()
        if not isinstance(body, dict):
            raise PollerError(400, "Request body must be a JSON object.")
        query = validate_query(body.get("query"))
        category_id = body.get("category_id") or ""
        if not isinstance(category_id, str) or len(category_id) > 40:
            raise PollerError(400, "category_id must be short text.")
        watch_id = get_poller().store.add_watch(query, category_id)
        return {"ok": True, "id": watch_id}
    except PollerError as e:
        return _err(e)
    except Exception:
        return _err(PollerError(400, "Request body must be valid JSON."))


@router.get("/admin/poller/watchlist")
def list_watches(request: Request):
    try:
        _check_admin(request)
        return {"ok": True, "watches": [_watch_json(w) for w in get_poller().store.list_watches()]}
    except PollerError as e:
        return _err(e)


@router.delete("/admin/poller/watchlist/{watch_id}")
def delete_watch(watch_id: int, request: Request):
    try:
        _check_admin(request)
        ok = get_poller().store.delete_watch(watch_id)
        if not ok:
            raise PollerError(404, "No such watch.")
        return {"ok": True}
    except PollerError as e:
        return _err(e)


@router.post("/admin/poller/watchlist/{watch_id}/enabled")
async def set_watch_enabled(watch_id: int, request: Request):
    try:
        _check_admin(request)
        body = await request.json()
        enabled = bool(body.get("enabled", True)) if isinstance(body, dict) else True
        if not get_poller().store.set_enabled(watch_id, enabled):
            raise PollerError(404, "No such watch.")
        return {"ok": True, "enabled": enabled}
    except PollerError as e:
        return _err(e)
    except Exception:
        return _err(PollerError(400, "Request body must be valid JSON."))


@router.post("/admin/poller/run")
async def run_poller(request: Request):
    try:
        _check_admin(request)
        force_all = request.query_params.get("force_all", "").lower() in ("1", "true", "yes")
        results = await run_in_threadpool(get_poller().run_due, force_all)
        pruned = await run_in_threadpool(get_poller().store.prune_stale)
        return {"ok": True, "runs": [_run_json(r) for r in results], "pruned_stale": pruned}
    except PollerError as e:
        return _err(e)


@router.get("/admin/poller/status")
def poller_status(request: Request):
    try:
        _check_admin(request)
        store = get_poller().store
        runs = store.recent_runs(limit=20)
        return {"ok": True, "recent_runs": [dict(r) for r in runs],
                "watch_count": len(store.list_watches()), "enabled_count": len(store.list_watches(True))}
    except PollerError as e:
        return _err(e)


@router.get("/admin/poller/trend")
def trend(request: Request):
    try:
        _check_admin(request)
        query = validate_query(request.query_params.get("query"))
        t = price_trend(get_poller().store, query)
        return {"ok": True, "query": t.query, "sample_count": t.sample_count,
                "recent_median": t.recent_median, "prior_median": t.prior_median,
                "trend_pct": t.trend_pct, "inferred_sold_count": t.inferred_sold_count,
                "window_days": t.window_days}
    except PollerError as e:
        return _err(e)


# --------------------------------------------------------------------------
# CLI entrypoint — for a system cron / scheduled job running directly
# against this service's database, no HTTP hop needed. See
# docs/COMPS_POLLER.md for the GitHub Actions alternative (hits
# /admin/poller/run over HTTP instead, for when the poller doesn't run on
# the same host as the cron trigger).
#
#     python3 -m comps_poller run [--force-all]
#     python3 -m comps_poller add "Pyrex 403 mixing bowl"
#     python3 -m comps_poller list
# --------------------------------------------------------------------------

def _cli(argv: List[str]) -> int:
    if not argv:
        print("usage: comps_poller <run|add|list> [args]", file=__import__("sys").stderr)
        return 2
    _use_env_ebay_credentials()
    store = PollerStore()
    cmd = argv[0]
    if cmd == "run":
        force_all = "--force-all" in argv[1:]
        results = ComPoller(store=store).run_due(force_all=force_all)
        pruned = store.prune_stale()
        for r in results:
            status = "BUDGET EXHAUSTED" if r.budget_exhausted else (r.error or "ok")
            print(f"watch {r.watch_id} ({r.query!r}): seen={r.seen} new={r.new_items} "
                  f"disappeared={r.disappeared_items} inferred_sold={r.inferred_sold} [{status}]")
        print(f"pruned {pruned} stale rows; {len(results)} watch(es) processed")
        return 0
    if cmd == "add":
        if len(argv) < 2:
            print("usage: comps_poller add <query> [category_id]", file=__import__("sys").stderr)
            return 2
        query = validate_query(argv[1])
        category_id = argv[2] if len(argv) > 2 else ""
        watch_id = store.add_watch(query, category_id)
        print(f"added watch {watch_id}: {query!r}")
        return 0
    if cmd == "list":
        for w in store.list_watches():
            state = "enabled" if w.enabled else "disabled"
            print(f"{w.id}\t{state}\t{w.query!r}\tlast_polled={w.last_polled_at}")
        return 0
    print(f"unknown command: {cmd!r}", file=__import__("sys").stderr)
    return 2


if __name__ == "__main__":
    import sys
    sys.exit(_cli(sys.argv[1:]))
