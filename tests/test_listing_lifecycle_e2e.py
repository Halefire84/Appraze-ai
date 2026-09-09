from flip_ledger import update_flip
from listing_bridge import build_master_listing
from listing_store import transition_listing, upsert_listing


def test_purchased_to_listed_builds_master_and_marketplace_draft():
    purchased = {
        "item_name": "Vintage Camera",
        "source": "hibid",
        "source_listing_id": "LOT-42",
        "source_url": "https://example.com/lot/42",
        "cost_basis": 30.0,
        "market_value": 100.0,
        "list_price": 89.99,
        "status": "PURCHASED",
    }

    listed = update_flip(purchased, status="LISTED")
    master = build_master_listing(listed)

    assert listed["status"] == "LISTED"
    assert master["sku"] == "LOT-42"
    assert master["price"] == 89.99
    assert master["source_url"].endswith("/42")

    drafts = upsert_listing([], {**master, "marketplace": "eBay", "status": "DRAFT"})
    ready = transition_listing(drafts[0], "READY_TO_PUBLISH")

    assert ready["status"] == "READY_TO_PUBLISH"
    assert ready["marketplace"] == "eBay"


def test_listing_cannot_skip_draft_to_active():
    draft = {"sku": "A1", "marketplace": "eBay", "status": "DRAFT"}

    try:
        transition_listing(draft, "ACTIVE")
    except ValueError as exc:
        assert "DRAFT -> ACTIVE" in str(exc)
    else:
        raise AssertionError("DRAFT must not jump directly to ACTIVE")
