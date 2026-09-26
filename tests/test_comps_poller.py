"""
Tests for comps_poller.py — the background eBay Browse-API history poller
(briefs/comps-collector-brief-2026-09-26.md). eBay is faked throughout (no
network).

    python3 -m pytest tests/test_comps_poller.py -v
"""

import os
import tempfile
import unittest
from unittest import mock

import requests
from fastapi.testclient import TestClient

import comps
import comps_adapters
import comps_poller
import stripe_webhook_server
from comps_poller import (
    ComPoller,
    PollerError,
    PollerCompsAdapter,
    PollerStore,
    normalize_title,
    price_trend,
    validate_query,
)
from pos_connect import RateLimiter


def listing(item_id, price, title="Pyrex 403 mixing bowl", shipping=0.0, condition="Used"):
    return {
        "source": "eBay", "source_listing_id": item_id, "url": f"https://www.ebay.com/itm/{item_id}",
        "title": title, "description": "", "category": "Kitchen", "price": price,
        "condition": condition, "shipping": shipping, "seller": "", "location": "",
        "images": [], "auction_end": None,
    }


class FakeListingsAdapter:
    def __init__(self, pages=None, exc=None):
        self.pages = pages or []  # list of "what fetch_listings returns", consumed in order
        self.exc = exc
        self.calls = []

    def fetch_listings(self, query, limit=20):
        self.calls.append((query, limit))
        if self.exc:
            raise self.exc
        if not self.pages:
            return []
        return self.pages.pop(0)


class TempStoreCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = PollerStore(os.path.join(self.tmp.name, "poller.sqlite3"))

    def tearDown(self):
        self.tmp.cleanup()


class TestNormalizeAndValidate(unittest.TestCase):
    def test_normalize_title_groups_near_identical_titles(self):
        self.assertEqual(normalize_title("Pyrex #403  Mixing-Bowl!!"), normalize_title("pyrex 403 mixing bowl"))
        self.assertEqual(normalize_title(""), "")
        self.assertEqual(normalize_title(None), "")

    def test_validate_query(self):
        self.assertEqual(validate_query("  lamp  "), "lamp")
        for bad in [None, 5, True, "", "a", "x" * 101]:
            with self.assertRaises(PollerError):
                validate_query(bad)


class TestWatchlist(TempStoreCase):
    def test_add_list_get_delete(self):
        wid = self.store.add_watch("Pyrex 403", "20648")
        watches = self.store.list_watches()
        self.assertEqual(len(watches), 1)
        self.assertEqual(watches[0].query, "Pyrex 403")
        self.assertEqual(self.store.get_watch(wid).id, wid)
        self.assertIsNone(self.store.get_watch(9999))
        self.assertTrue(self.store.set_enabled(wid, False))
        self.assertFalse(self.store.get_watch(wid).enabled)
        self.assertFalse(self.store.set_enabled(9999, True))
        self.assertTrue(self.store.delete_watch(wid))
        self.assertFalse(self.store.delete_watch(wid))
        self.assertEqual(self.store.list_watches(), [])

    def test_due_watches_respects_interval_and_never_polled(self):
        wid1 = self.store.add_watch("never polled yet")
        wid2 = self.store.add_watch("polled recently")
        wid3 = self.store.add_watch("polled long ago")
        with mock.patch("comps_poller.utc_now", return_value=comps_poller.parse_iso("2026-01-01T12:00:00+00:00")):
            self.store.touch_watch_polled(wid2, comps_poller.utc_now())
        with mock.patch("comps_poller.utc_now", return_value=comps_poller.parse_iso("2026-01-01T06:00:00+00:00")):
            self.store.touch_watch_polled(wid3, comps_poller.utc_now())
        with mock.patch("comps_poller.utc_now", return_value=comps_poller.parse_iso("2026-01-01T12:05:00+00:00")):
            due = {w.id for w in self.store.due_watches(interval_minutes=240)}
        self.assertIn(wid1, due)  # never polled -> always due
        self.assertNotIn(wid2, due)  # polled 5 min ago, interval 4h -> not due
        self.assertIn(wid3, due)  # polled 6h5m ago -> due

    def test_disabled_watch_never_due(self):
        wid = self.store.add_watch("disabled one")
        self.store.set_enabled(wid, False)
        self.assertEqual(self.store.due_watches(interval_minutes=0), [])


class TestSnapshotsAndInference(TempStoreCase):
    def poll1(self, when, watch, items):
        seen = set()
        for it in items:
            self.store.upsert_seen(watch, it, when)
            seen.add(it["source_listing_id"])
        return seen

    def test_new_item_recorded_then_price_update_on_resight(self):
        wid = self.store.add_watch("lamp")
        watch = self.store.get_watch(wid)
        t1 = comps_poller.parse_iso("2026-01-01T00:00:00+00:00")
        is_new = self.store.upsert_seen(watch, listing("A1", 40.0), t1)
        self.assertTrue(is_new)
        row = self.store.get_snapshot("A1")
        self.assertEqual(row["times_seen"], 1)
        self.assertEqual(row["price"], 40.0)

        t2 = comps_poller.parse_iso("2026-01-02T00:00:00+00:00")
        is_new2 = self.store.upsert_seen(watch, listing("A1", 35.0), t2)
        self.assertFalse(is_new2)
        row2 = self.store.get_snapshot("A1")
        self.assertEqual(row2["times_seen"], 2)
        self.assertEqual(row2["price"], 35.0)  # latest asking price, not the first
        self.assertEqual(row2["still_active"], 1)

    def test_disappearance_below_sighting_threshold_is_not_inferred_sold(self):
        """Seen once, then gone: too noisy to call it sold (could just be
        search ranking churn) -- still_active flips, inferred_sold does not."""
        wid = self.store.add_watch("lamp")
        watch = self.store.get_watch(wid)
        t1 = comps_poller.parse_iso("2026-01-01T00:00:00+00:00")
        self.store.upsert_seen(watch, listing("A1", 40.0), t1)
        t2 = comps_poller.parse_iso("2026-01-02T00:00:00+00:00")
        disappeared, inferred = self.store.mark_disappeared(wid, seen_ids=set(), when=t2)
        self.assertEqual((disappeared, inferred), (1, 0))
        row = self.store.get_snapshot("A1")
        self.assertEqual(row["still_active"], 0)
        self.assertEqual(row["inferred_sold"], 0)
        self.assertEqual(row["disappeared_at"], comps_poller.iso(t2))

    def test_disappearance_at_or_above_threshold_is_inferred_sold(self):
        wid = self.store.add_watch("lamp")
        watch = self.store.get_watch(wid)
        t1 = comps_poller.parse_iso("2026-01-01T00:00:00+00:00")
        t2 = comps_poller.parse_iso("2026-01-02T00:00:00+00:00")
        t3 = comps_poller.parse_iso("2026-01-03T00:00:00+00:00")
        self.store.upsert_seen(watch, listing("A1", 40.0), t1)
        self.store.upsert_seen(watch, listing("A1", 38.0), t2)  # 2nd sighting
        disappeared, inferred = self.store.mark_disappeared(wid, seen_ids=set(), when=t3)
        self.assertEqual((disappeared, inferred), (1, 1))
        row = self.store.get_snapshot("A1")
        self.assertEqual(row["inferred_sold"], 1)
        self.assertEqual(row["price"], 38.0)  # "sold at last-seen price"

    def test_resighting_a_previously_disappeared_item_clears_inference(self):
        wid = self.store.add_watch("lamp")
        watch = self.store.get_watch(wid)
        t1, t2, t3 = [comps_poller.parse_iso(f"2026-01-0{n}T00:00:00+00:00") for n in (1, 2, 3)]
        self.store.upsert_seen(watch, listing("A1", 40.0), t1)
        self.store.upsert_seen(watch, listing("A1", 38.0), t2)
        self.store.mark_disappeared(wid, seen_ids=set(), when=t3)
        self.assertEqual(self.store.get_snapshot("A1")["inferred_sold"], 1)

        t4 = comps_poller.parse_iso("2026-01-04T00:00:00+00:00")
        self.store.upsert_seen(watch, listing("A1", 30.0), t4)  # relisted / still there after all
        row = self.store.get_snapshot("A1")
        self.assertEqual(row["still_active"], 1)
        self.assertEqual(row["inferred_sold"], 0)
        self.assertIsNone(row["disappeared_at"])

    def test_mark_disappeared_only_touches_its_own_watch(self):
        w1 = self.store.get_watch(self.store.add_watch("lamp"))
        w2 = self.store.get_watch(self.store.add_watch("bowl"))
        t1 = comps_poller.parse_iso("2026-01-01T00:00:00+00:00")
        self.store.upsert_seen(w1, listing("A1", 10.0), t1)
        self.store.upsert_seen(w2, listing("B1", 20.0), t1)
        t2 = comps_poller.parse_iso("2026-01-02T00:00:00+00:00")
        disappeared, _ = self.store.mark_disappeared(w1.id, seen_ids=set(), when=t2)
        self.assertEqual(disappeared, 1)
        self.assertEqual(self.store.get_snapshot("A1")["still_active"], 0)
        self.assertEqual(self.store.get_snapshot("B1")["still_active"], 1)  # untouched, different watch

    def test_prune_stale_drops_long_untouched_active_rows(self):
        wid = self.store.add_watch("lamp")
        watch = self.store.get_watch(wid)
        old = comps_poller.parse_iso("2026-01-01T00:00:00+00:00")
        self.store.upsert_seen(watch, listing("OLD", 10.0), old)
        with mock.patch("comps_poller.utc_now", return_value=comps_poller.parse_iso("2026-03-01T00:00:00+00:00")):
            pruned = self.store.prune_stale(older_than_days=45)
        self.assertEqual(pruned, 1)
        self.assertIsNone(self.store.get_snapshot("OLD"))


class TestPollerCompsAdapterHonesty(TempStoreCase):
    """The critical rule from the module docstring: inferred-sold items are
    NEVER handed to comps.py as SOLD (or at all, beyond honestly-active
    ones) -- they'd inflate comps.py's confidence math with unproven data."""

    def test_only_still_active_rows_are_returned_and_always_as_active(self):
        wid = self.store.add_watch("lamp")
        watch = self.store.get_watch(wid)
        t1, t2, t3 = [comps_poller.parse_iso(f"2026-01-0{n}T00:00:00+00:00") for n in (1, 2, 3)]
        self.store.upsert_seen(watch, listing("STILL_HERE", 25.0), t1)
        self.store.upsert_seen(watch, listing("GONE", 40.0), t1)
        self.store.upsert_seen(watch, listing("GONE", 38.0), t2)  # 2 sightings -> will be inferred sold
        self.store.upsert_seen(watch, listing("STILL_HERE", 25.0), t3)
        self.store.mark_disappeared(wid, seen_ids={"STILL_HERE"}, when=t3)
        self.assertEqual(self.store.get_snapshot("GONE")["inferred_sold"], 1)

        adapter = PollerCompsAdapter(store=self.store)
        with mock.patch("comps_poller.utc_now", return_value=t3):
            found = adapter.fetch_comps("lamp")
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0].price, 25.0)
        self.assertEqual(found[0].listing_type, comps.ACTIVE)
        # Never comps.SOLD, no matter what's in the store:
        self.assertTrue(all(c.listing_type == comps.ACTIVE for c in found))

    def test_summary_confidence_is_not_inflated_by_inferred_sold_rows(self):
        """End-to-end: even feeding the adapter's own output through
        comps.summarize_comps (which trusts listing_type==SOLD as real
        evidence) never reaches "sold" confidence from inferred data."""
        wid = self.store.add_watch("lamp")
        watch = self.store.get_watch(wid)
        t1 = comps_poller.parse_iso("2026-01-01T00:00:00+00:00")
        for i in range(10):
            self.store.upsert_seen(watch, listing(f"A{i}", 20.0 + i), t1)
        adapter = PollerCompsAdapter(store=self.store)
        with mock.patch("comps_poller.utc_now", return_value=t1):
            summary = comps.summarize_comps(adapter.fetch_comps("lamp"))
        self.assertEqual(summary.sold_count, 0)
        self.assertEqual(summary.confidence, comps.CONFIDENCE_LOW)  # asking prices only


class TestPollWatch(TempStoreCase):
    def test_successful_poll_records_new_items_and_spends_one_call(self):
        wid = self.store.add_watch("lamp")
        adapter = FakeListingsAdapter(pages=[[listing("A1", 20.0), listing("A2", 25.0)]])
        poller = ComPoller(store=self.store, adapter=adapter, limiter=RateLimiter(), daily_budget=10)
        result = poller.poll_watch(self.store.get_watch(wid))
        self.assertEqual(result.calls_made, 1)
        self.assertEqual(result.seen, 2)
        self.assertEqual(result.new_items, 2)
        self.assertFalse(result.budget_exhausted)
        self.assertIsNotNone(self.store.get_watch(wid).last_polled_at)

    def test_two_polls_detect_a_disappearance(self):
        wid = self.store.add_watch("lamp")
        watch = self.store.get_watch(wid)
        adapter = FakeListingsAdapter(pages=[
            [listing("A1", 20.0), listing("A2", 25.0)],
            [listing("A1", 20.0)],  # A2 vanished
        ])
        poller = ComPoller(store=self.store, adapter=adapter, limiter=RateLimiter(), daily_budget=10)
        r1 = poller.poll_watch(watch)
        self.assertEqual(r1.disappeared_items, 0)
        r2 = poller.poll_watch(self.store.get_watch(wid))
        self.assertEqual(r2.disappeared_items, 1)
        self.assertEqual(r2.inferred_sold, 0)  # A2 was only seen once before vanishing

    def test_budget_exhausted_makes_zero_calls(self):
        wid = self.store.add_watch("lamp")
        adapter = FakeListingsAdapter(pages=[[listing("A1", 20.0)]])
        poller = ComPoller(store=self.store, adapter=adapter, limiter=RateLimiter(), daily_budget=0)
        result = poller.poll_watch(self.store.get_watch(wid))
        self.assertTrue(result.budget_exhausted)
        self.assertEqual(result.calls_made, 0)
        self.assertEqual(adapter.calls, [])

    def test_ebay_not_configured_is_recorded_as_error_not_a_crash(self):
        wid = self.store.add_watch("lamp")
        adapter = FakeListingsAdapter(exc=comps_adapters.EbayAuthError("no keys"))
        poller = ComPoller(store=self.store, adapter=adapter, limiter=RateLimiter(), daily_budget=10)
        result = poller.poll_watch(self.store.get_watch(wid))
        self.assertIn("not configured", result.error)

    def test_network_error_is_recorded_as_error_not_a_crash(self):
        wid = self.store.add_watch("lamp")
        adapter = FakeListingsAdapter(exc=requests.ConnectionError())
        poller = ComPoller(store=self.store, adapter=adapter, limiter=RateLimiter(), daily_budget=10)
        result = poller.poll_watch(self.store.get_watch(wid))
        self.assertIsNotNone(result.error)

    def test_run_due_only_polls_due_watches_unless_forced(self):
        w1 = self.store.add_watch("due")
        w2 = self.store.add_watch("not due")
        with mock.patch("comps_poller.utc_now", return_value=comps_poller.parse_iso("2026-01-01T00:00:00+00:00")):
            self.store.touch_watch_polled(w2, comps_poller.utc_now())
        adapter = FakeListingsAdapter(pages=[[], []])
        poller = ComPoller(store=self.store, adapter=adapter, limiter=RateLimiter(), daily_budget=10,
                           poll_interval_minutes=240)
        with mock.patch("comps_poller.utc_now", return_value=comps_poller.parse_iso("2026-01-01T00:05:00+00:00")):
            results = poller.run_due()
        self.assertEqual([r.watch_id for r in results], [w1])
        adapter.pages = [[]]
        with mock.patch("comps_poller.utc_now", return_value=comps_poller.parse_iso("2026-01-01T00:05:00+00:00")):
            results_forced = poller.run_due(force_all=True)
        self.assertEqual(sorted(r.watch_id for r in results_forced), [w1, w2])

    def test_records_run_log(self):
        wid = self.store.add_watch("lamp")
        adapter = FakeListingsAdapter(pages=[[listing("A1", 20.0)]])
        poller = ComPoller(store=self.store, adapter=adapter, limiter=RateLimiter(), daily_budget=10)
        poller.poll_watch(self.store.get_watch(wid))
        runs = self.store.recent_runs()
        self.assertEqual(len(runs), 1)
        self.assertEqual(runs[0]["query"], "lamp")
        self.assertEqual(runs[0]["new_items"], 1)


class TestPriceTrend(TempStoreCase):
    def test_recent_vs_prior_median_and_trend_direction(self):
        wid = self.store.add_watch("lamp")
        watch = self.store.get_watch(wid)
        # "Prior" window (31-60 days ago): cheaper. "Recent" window (0-30 days ago): pricier.
        with mock.patch("comps_poller.utc_now", return_value=comps_poller.parse_iso("2026-01-01T00:00:00+00:00")):
            now = comps_poller.utc_now()
        prior_time = comps_poller.iso(now.fromtimestamp(now.timestamp() - 45 * 86400, tz=now.tzinfo))
        recent_time = comps_poller.iso(now.fromtimestamp(now.timestamp() - 5 * 86400, tz=now.tzinfo))
        for i, p in enumerate([10.0, 12.0, 14.0]):
            self.store.upsert_seen(watch, listing(f"P{i}", p), comps_poller.parse_iso(prior_time))
        for i, p in enumerate([20.0, 22.0, 24.0]):
            self.store.upsert_seen(watch, listing(f"R{i}", p), comps_poller.parse_iso(recent_time))
        with mock.patch("comps_poller.utc_now", return_value=comps_poller.parse_iso("2026-01-01T00:00:00+00:00")):
            t = price_trend(self.store, "lamp", window_days=60, split_days=30)
        self.assertEqual(t.prior_median, 12.0)
        self.assertEqual(t.recent_median, 22.0)
        self.assertGreater(t.trend_pct, 0)
        self.assertEqual(t.sample_count, 6)

    def test_no_data_returns_none_not_zero(self):
        t = price_trend(self.store, "nothing tracked")
        self.assertIsNone(t.recent_median)
        self.assertIsNone(t.prior_median)
        self.assertIsNone(t.trend_pct)
        self.assertEqual(t.sample_count, 0)

    def test_inferred_sold_count_reflected_in_trend(self):
        wid = self.store.add_watch("lamp")
        watch = self.store.get_watch(wid)
        t1, t2, t3 = [comps_poller.parse_iso(f"2026-01-0{n}T00:00:00+00:00") for n in (1, 2, 3)]
        self.store.upsert_seen(watch, listing("A1", 10.0), t1)
        self.store.upsert_seen(watch, listing("A1", 9.0), t2)
        self.store.mark_disappeared(wid, seen_ids=set(), when=t3)
        with mock.patch("comps_poller.utc_now", return_value=t3):
            t = price_trend(self.store, "lamp")
        self.assertEqual(t.inferred_sold_count, 1)


class TestEnvCredentials(unittest.TestCase):
    def test_wires_env_credentials_into_adapters(self):
        orig = comps_adapters._ebay_client_credentials
        try:
            comps_poller._use_env_ebay_credentials()
            with mock.patch.dict(os.environ, {"EBAY_CLIENT_ID": "i", "EBAY_CLIENT_SECRET": "s"}):
                self.assertEqual(comps_adapters._ebay_client_credentials(), ("i", "s"))
        finally:
            comps_adapters._ebay_client_credentials = orig


class TestHttp(unittest.TestCase):
    ADMIN_TOKEN = "test-admin-token"

    def setUp(self):
        self.env = mock.patch.dict(os.environ, {"COMPS_POLLER_ADMIN_TOKEN": self.ADMIN_TOKEN})
        self.env.start()
        self.tmp = tempfile.TemporaryDirectory()
        self.store = PollerStore(os.path.join(self.tmp.name, "poller.sqlite3"))
        self.adapter = FakeListingsAdapter(pages=[])
        self.poller = ComPoller(store=self.store, adapter=self.adapter, limiter=RateLimiter(), daily_budget=10)
        comps_poller.set_poller(self.poller)
        self.client = TestClient(stripe_webhook_server.app)

    def tearDown(self):
        comps_poller.set_poller(None)
        self.env.stop()
        self.tmp.cleanup()

    def auth(self):
        return {"Authorization": f"Bearer {self.ADMIN_TOKEN}"}

    def test_no_admin_token_configured_is_503(self):
        with mock.patch.dict(os.environ, {"COMPS_POLLER_ADMIN_TOKEN": ""}):
            r = self.client.get("/admin/poller/watchlist", headers=self.auth())
        self.assertEqual(r.status_code, 503)

    def test_wrong_or_missing_token_is_401(self):
        self.assertEqual(self.client.get("/admin/poller/watchlist").status_code, 401)
        r = self.client.get("/admin/poller/watchlist", headers={"Authorization": "Bearer wrong"})
        self.assertEqual(r.status_code, 401)

    def test_add_list_delete_watch(self):
        r = self.client.post("/admin/poller/watchlist", json={"query": "Pyrex 403"}, headers=self.auth())
        self.assertEqual(r.status_code, 200, r.text)
        wid = r.json()["id"]
        listed = self.client.get("/admin/poller/watchlist", headers=self.auth()).json()["watches"]
        self.assertEqual(len(listed), 1)
        self.assertEqual(listed[0]["query"], "Pyrex 403")
        r = self.client.delete(f"/admin/poller/watchlist/{wid}", headers=self.auth())
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self.client.delete(f"/admin/poller/watchlist/{wid}", headers=self.auth()).status_code, 404)

    def test_add_watch_validates_query(self):
        r = self.client.post("/admin/poller/watchlist", json={"query": ""}, headers=self.auth())
        self.assertEqual(r.status_code, 400)
        r = self.client.post("/admin/poller/watchlist", json={"query": "x" * 200}, headers=self.auth())
        self.assertEqual(r.status_code, 400)

    def test_set_enabled(self):
        wid = self.client.post("/admin/poller/watchlist", json={"query": "lamp"}, headers=self.auth()).json()["id"]
        r = self.client.post(f"/admin/poller/watchlist/{wid}/enabled", json={"enabled": False}, headers=self.auth())
        self.assertEqual(r.status_code, 200)
        self.assertFalse(self.store.get_watch(wid).enabled)

    def test_run_triggers_poller_and_returns_results(self):
        self.client.post("/admin/poller/watchlist", json={"query": "lamp"}, headers=self.auth())
        self.adapter.pages = [[listing("A1", 20.0)]]
        r = self.client.post("/admin/poller/run", headers=self.auth())
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertEqual(len(body["runs"]), 1)
        self.assertEqual(body["runs"][0]["new_items"], 1)

    def test_status_reports_recent_runs(self):
        self.client.post("/admin/poller/watchlist", json={"query": "lamp"}, headers=self.auth())
        self.adapter.pages = [[]]
        self.client.post("/admin/poller/run", headers=self.auth())
        r = self.client.get("/admin/poller/status", headers=self.auth())
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.json()["recent_runs"]), 1)
        self.assertEqual(r.json()["watch_count"], 1)

    def test_trend_endpoint(self):
        r = self.client.get("/admin/poller/trend", params={"query": "lamp"}, headers=self.auth())
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["query"], "lamp")
        self.assertIsNone(r.json()["recent_median"])

    def test_public_comps_search_endpoint_still_works_alongside_admin_routes(self):
        # Sanity check the admin router mount didn't break the existing
        # public comps collector endpoint (different auth model entirely).
        r = self.client.post("/comps/search", json={"query": ""})
        self.assertEqual(r.status_code, 400)

    def test_malformed_json_body_is_400_not_500(self):
        r = self.client.post("/admin/poller/watchlist", content=b"not json", headers=self.auth())
        self.assertEqual(r.status_code, 400)


class TestCli(TempStoreCase):
    def run_cli(self, argv):
        with mock.patch("comps_poller.PollerStore", return_value=self.store):
            return comps_poller._cli(argv)

    def test_add_and_list(self):
        self.assertEqual(self.run_cli(["add", "Pyrex 403"]), 0)
        self.assertEqual(len(self.store.list_watches()), 1)
        self.assertEqual(self.run_cli(["list"]), 0)

    def test_add_requires_query_arg(self):
        self.assertEqual(self.run_cli(["add"]), 2)

    def test_unknown_command(self):
        self.assertEqual(self.run_cli(["bogus"]), 2)

    def test_no_args(self):
        self.assertEqual(self.run_cli([]), 2)

    def test_run_smoke(self):
        self.store.add_watch("lamp")
        with mock.patch("comps_poller.ComPoller") as MockPoller:
            instance = MockPoller.return_value
            instance.run_due.return_value = []
            self.assertEqual(self.run_cli(["run"]), 0)
            instance.run_due.assert_called_once_with(force_all=False)

    def test_run_force_all_flag(self):
        with mock.patch("comps_poller.ComPoller") as MockPoller:
            instance = MockPoller.return_value
            instance.run_due.return_value = []
            self.run_cli(["run", "--force-all"])
            instance.run_due.assert_called_once_with(force_all=True)
