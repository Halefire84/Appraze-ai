from opportunity_radar import analyze_listing, detect_category_mismatch, detect_typos


def test_common_typo_is_flagged():
    signals = detect_typos("Vintage reciever", "Works great")
    assert any(signal.code == "title_description_typo" for signal in signals)


def test_title_description_mismatch_is_flagged():
    result = analyze_listing({
        "title": "Rolex Submariner",
        "description": "Old kitchen cabinet with wood shelves and brass handles.",
    })
    assert any(signal.code == "title_description_mismatch" for signal in result.signals)
    assert result.review_required


def test_category_mismatch_is_flagged():
    signals = detect_category_mismatch(
        "Furniture",
        ["watch", "rolex"],
        "Rolex watch",
        "Mechanical wristwatch",
    )
    assert any(signal.code == "possible_misclassification" for signal in signals)


def test_value_gap_can_surface_opportunity():
    result = analyze_listing({
        "title": "Vintage watch",
        "description": "Needs gone today",
        "price": 100,
        "estimated_value": 350,
    })
    assert result.opportunity_score >= 25
    assert result.review_required


def test_bulk_lot_is_flagged_even_without_a_category():
    result = analyze_listing({
        "title": "Lot of assorted laptops",
        "description": "Untested warehouse liquidation, 25 units.",
        "price": 150,
    })
    assert any(signal.code == "bulk_quantity" for signal in result.signals)
    assert any(signal.code == "liquidation_lot" for signal in result.signals)
    assert result.review_required


def test_brand_hidden_in_description_is_flagged():
    result = analyze_listing({
        "title": "Old stereo receiver",
        "description": "Marantz model 2270, powers on. Estate sale.",
        "price": 40,
    })
    assert any(signal.code == "brand_hidden_in_description" for signal in result.signals)
    assert any(signal.code == "model_number_hidden" for signal in result.signals)


def test_precious_material_marker_is_supported_beyond_gold():
    result = analyze_listing({
        "title": "Old silver bracelet",
        "description": "Marked 925 sterling, estate piece.",
        "price": 20,
    })
    assert any(signal.code == "precious_material_present" for signal in result.signals)
