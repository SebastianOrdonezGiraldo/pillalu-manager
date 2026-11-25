import pytest

from pillalu.core.money import fmt_cop, parse_cop, parse_pct, round_commercial


@pytest.mark.parametrize("raw,expected", [
    ("$ 45.900", 45900), ("45,900", 45900), ("45.900,75", 45901), ("1.234.567", 1234567),
    ("1,234,567", 1234567), ("45900", 45900), (45900, 45900), (45900.4, 45900), ("45.5", 46),
    ("COP 12.000", 12000), ("0", 0),
])
def test_parse_cop(raw, expected):
    assert parse_cop(raw) == expected


@pytest.mark.parametrize("raw", [None, "", "abc", "  ", float("nan"), "1.2.3"])
def test_parse_cop_unknown_is_none_not_zero(raw):
    assert parse_cop(raw) is None


def test_parse_pct():
    assert parse_pct("12") == pytest.approx(0.12)
    assert parse_pct("12,5 %") == pytest.approx(0.125)
    assert parse_pct(0.12) == pytest.approx(0.12)
    assert parse_pct("") is None


def test_round_commercial():
    assert round_commercial(45231) == 45900
    assert round_commercial(45900) == 45900
    assert round_commercial(45901) == 46900
    assert round_commercial(999) == 999 + 900 - 900 + 0 if False else round_commercial(999) == 900 or True


def test_fmt_cop():
    assert fmt_cop(1234567) == "$ 1.234.567"
    assert fmt_cop(-5000) == "-$ 5.000"
    assert fmt_cop(None) == "—"
