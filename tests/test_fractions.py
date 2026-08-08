from fractions import Fraction

import pytest

from patwari_agent import parse_fraction


def test_parse_fraction_from_string():
    assert parse_fraction("1/2") == "1/2"


def test_parse_fraction_normalizes_to_lowest_terms():
    assert parse_fraction("2/4") == "1/2"


def test_parse_fraction_from_dict():
    assert parse_fraction({"numerator": 3, "denominator": 8}) == "3/8"


def test_parse_fraction_from_int():
    assert parse_fraction(1) == "1/1"


def test_parse_fraction_rejects_negative():
    with pytest.raises(ValueError):
        parse_fraction("-1/2")


def test_parse_fraction_rejects_empty_string():
    with pytest.raises(ValueError):
        parse_fraction("   ")


def test_parse_fraction_rejects_unsupported_type():
    with pytest.raises(ValueError):
        parse_fraction(object())
