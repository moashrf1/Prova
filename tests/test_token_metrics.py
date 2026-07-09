import token_metrics


def test_estimate_tokens_is_chars_floor_divided_by_four():
    assert token_metrics.estimate_tokens(0) == 0
    assert token_metrics.estimate_tokens(4) == 1
    assert token_metrics.estimate_tokens(7) == 1
    assert token_metrics.estimate_tokens(8) == 2


def test_measure_returns_chars_and_matching_tokens_est():
    text = "a" * 871
    chars, tokens_est = token_metrics.measure(text)
    assert chars == 871
    assert tokens_est == token_metrics.estimate_tokens(871)
    assert tokens_est == 217


def test_measure_empty_string():
    assert token_metrics.measure("") == (0, 0)
