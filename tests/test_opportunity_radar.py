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
