from source_registry import SourceDefinition, SourceRegistry, default_source_registry


def test_default_registry_contains_core_and_surplus_sources():
    registry = default_source_registry()
    keys = {source.key for source in registry.all()}
    assert {"ebay", "ctbids", "shopgoodwill", "hibid", "gsa", "govdeals"}.issubset(keys)


def test_only_configured_enabled_sources_are_automated():
    registry = default_source_registry()
    enabled = registry.enabled()
    assert len(enabled) == 1
    assert enabled[0].key == "ebay"


def test_registry_can_add_a_new_legitimate_source_without_changing_radar():
    registry = SourceRegistry([])
    registry.register(SourceDefinition(
        key="local_charity",
        name="Local Charity Auction",
        source_type="charity_auction",
        acquisition_methods=("public_catalog",),
        source_url="https://example.com/auction",
    ))
    assert registry.get("local_charity").name == "Local Charity Auction"
    assert registry.enabled() == []
