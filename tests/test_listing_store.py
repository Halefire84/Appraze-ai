from listing_store import mark_item_sold, transition_listing, upsert_listing


def test_upsert_replaces_same_marketplace():
    rows = [{"sku": "A1", "marketplace": "eBay", "status": "DRAFT", "price": 10}]
    rows = upsert_listing(rows, {"sku": "A1", "marketplace": "eBay", "status": "ACTIVE", "price": 20})
    assert len(rows) == 1
    assert rows[0]["status"] == "ACTIVE"
    assert rows[0]["price"] == 20


def test_transition_preserves_external_id():
    # READY_TO_PUBLISH, not DRAFT: the lifecycle hardening in listing_store.py
    # (see tests/test_listing_lifecycle_e2e.py::test_listing_cannot_skip_draft_to_active)
    # deliberately requires DRAFT -> READY_TO_PUBLISH -> ACTIVE, matching every
    # real caller (crtc.py, pages/5_Cross_List.py only ever request
    # READY_TO_PUBLISH). This test predates that hardening; the scenario is
    # updated to a valid transition, the behavior under test (external_id is
    # set, status updates, the input dict is not mutated) is unchanged.
    row = {"sku": "A1", "marketplace": "eBay", "status": "READY_TO_PUBLISH"}
    updated = transition_listing(row, "ACTIVE", external_id="EB123")
    assert updated["status"] == "ACTIVE"
    assert updated["external_id"] == "EB123"
    assert row["status"] == "READY_TO_PUBLISH"


def test_mark_sold_flags_active_listings():
    rows = [
        {"sku": "A1", "marketplace": "eBay", "status": "ACTIVE"},
        {"sku": "A1", "marketplace": "Mercari", "status": "READY_TO_PUBLISH"},
        {"sku": "A1", "marketplace": "Etsy", "status": "DEACTIVATED"},
    ]
    updated = mark_item_sold(rows)
    assert [r["status"] for r in updated] == ["SOLD", "SOLD", "DEACTIVATED"]
