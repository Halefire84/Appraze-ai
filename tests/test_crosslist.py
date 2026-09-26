"""Scaffold tests for the cross-listing package.

Pure and offline: no network, no credentials, no publishing. Formatting is
always allowed; publish/delist must refuse while the feature flag is off.
"""

import pytest

from crosslist import config, depop, models, registry, tracker
from crosslist.base import CrosslistDisabledError, NotConfiguredError


def _master(**kwargs):
    args = {
        "title": "Vintage denim jacket",
        "description": "Great condition, light wear.",
        "price": 45.0,
        "photos": ["https://example.com/p1.jpg"],
        "category": "Jackets",
        "brand": "Levi's",
    }
    args.update(kwargs)
    return models.MasterListing(**args)


def test_flag_defaults_off(monkeypatch):
    monkeypatch.delenv("APPRAZE_CROSSLIST", raising=False)
    assert config.crosslisting_enabled() is False


def test_flag_on(monkeypatch):
    monkeypatch.setenv("APPRAZE_CROSSLIST", "1")
    assert config.crosslisting_enabled() is True


def test_model_validation_rejects_bad_input():
    with pytest.raises(models.ValidationError):
        _master(title="  ").validate()
    with pytest.raises(models.ValidationError):
        _master(price=0).validate()
    with pytest.raises(models.ValidationError):
        _master(photos=[]).validate()
    with pytest.raises(models.ValidationError):
        _master(quantity=0).validate()


def test_model_validation_accepts_good_input():
    _master().validate()


def test_registry_lists_six_coming_soon():
    infos = registry.list_marketplaces()
    assert {i["id"] for i in infos} == {
        "ebay",
        "etsy",
        "depop",
        "poshmark",
        "mercari",
        "facebook",
    }
    assert all(i["status"] == "coming_soon" for i in infos)


def test_get_adapter_unknown_marketplace():
    with pytest.raises(ValueError):
        registry.get_adapter("not-a-marketplace")


def test_gated_adapter_refuses_when_flag_off(monkeypatch):
    monkeypatch.delenv("APPRAZE_CROSSLIST", raising=False)
    with pytest.raises(CrosslistDisabledError):
        registry.get_adapter_gated("ebay")


def test_publish_refuses_when_flag_off(monkeypatch):
    monkeypatch.delenv("APPRAZE_CROSSLIST", raising=False)
    adapter = registry.get_adapter("ebay")
    formatted = adapter.format_listing(_master())  # formatting is always allowed
    with pytest.raises(CrosslistDisabledError):
        adapter.publish(formatted)


def test_publish_raises_not_configured_when_flag_on(monkeypatch):
    monkeypatch.setenv("APPRAZE_CROSSLIST", "1")
    adapter = registry.get_adapter("ebay")
    formatted = adapter.format_listing(_master())
    with pytest.raises(NotConfiguredError):
        adapter.publish(formatted)


def test_ebay_payload_structure():
    formatted = registry.get_adapter("ebay").format_listing(_master(sku="SKU-1"))
    assert formatted.marketplace_id == "ebay"
    item = formatted.payload["inventory_item"]
    assert item["product"]["title"] == "Vintage denim jacket"
    assert formatted.payload["offer"]["marketplaceId"] == "EBAY_US"


def test_etsy_payload_structure():
    formatted = registry.get_adapter("etsy").format_listing(_master())
    assert formatted.marketplace_id == "etsy"
    assert formatted.payload["listing"]["title"] == "Vintage denim jacket"
    assert formatted.payload["listing"]["price"] == 45.0


def test_depop_stub_refuses_everything(monkeypatch):
    adapter = registry.get_adapter("depop")
    with pytest.raises(depop.DepopNotAvailableError):
        adapter.format_listing(_master())
    monkeypatch.setenv("APPRAZE_CROSSLIST", "1")
    with pytest.raises(depop.DepopNotAvailableError):
        adapter.publish(None)


@pytest.mark.parametrize("mid", ["poshmark", "mercari", "facebook"])
def test_assisted_payload_has_deep_link_and_clipboard(mid):
    formatted = registry.get_adapter(mid).format_listing(_master())
    assert formatted.marketplace_id == mid
    assert formatted.assist["deep_link"].startswith("https://")
    assert "Vintage denim jacket" in formatted.assist["clipboard_text"]
    assert "45.00" in formatted.assist["clipboard_text"]


def test_tracker_roundtrip():
    t = tracker.DelistTracker()
    t.record("item-1", "poshmark")
    t.mark_live("item-1", "poshmark", external_id="pm-123")
    rec = t.get("item-1", "poshmark")
    assert rec is not None and rec.status == "live" and rec.external_id == "pm-123"
    t.mark_delisted("item-1", "poshmark")
    assert t.get("item-1", "poshmark").status == "delisted"
    assert t.for_item("item-1") and t.all()
