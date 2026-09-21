from ai_usage import INPUT_USD_PER_MTOK, OUTPUT_USD_PER_MTOK, UsageDecision


def test_usage_decision_defaults_to_denied():
    decision = UsageDecision(False, "limit")
    assert not decision.allowed
    assert decision.monthly_used == 0


def test_sonnet5_cost_formula_matches_configured_rates():
    input_tokens = 100_000
    output_tokens = 900
    cost = (input_tokens / 1_000_000) * INPUT_USD_PER_MTOK + (
        output_tokens / 1_000_000
    ) * OUTPUT_USD_PER_MTOK
    assert round(cost, 6) == 0.209


def test_image_and_description_limits_are_bounded():
    from ai_usage import MAX_DESCRIPTION_CHARS, MAX_IMAGE_BYTES

    assert MAX_IMAGE_BYTES == 3_000_000
    assert MAX_DESCRIPTION_CHARS == 2_000
