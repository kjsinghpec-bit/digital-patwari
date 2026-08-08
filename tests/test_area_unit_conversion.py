"""TEST 6, 8, 9 (per the domain-model incorporation request): exact
Kanal/Marla/Sarsahi arithmetic, and the decimal-Kanal / decimal-Marla
conversion rules that must NOT be read as if the decimal digits were
literal Marla/Sarsahi counts."""
from fractions import Fraction

from patwari_agent import AreaKanalMarlaSarsahi
from digital_patwari.normalization import (
    decimal_kanal_to_kanal_marla,
    decimal_kanal_to_sarsahi,
    decimal_marla_to_marla_sarsahi,
)


# TEST 6: 15 Kanal 12 Marla converts exactly to 312 Marla.
def test_kanal_marla_converts_exactly_to_whole_marla():
    area = AreaKanalMarlaSarsahi(kanal=15, marla=12)
    assert area.total_marla() == 312  # (15*20)+12


# TEST 8: decimal Kanal must not be read as literal Marla digits.
def test_decimal_kanal_10_55_is_not_10_kanal_55_marla():
    kanal, marla = decimal_kanal_to_kanal_marla("10.55")
    assert kanal == 10
    assert marla == Fraction(11, 1)  # 0.55 * 20 = 11, NOT 55


def test_decimal_kanal_conversion_is_exact_not_float_noise():
    kanal, marla = decimal_kanal_to_kanal_marla("15.6")
    assert kanal == 15
    assert marla == Fraction(12, 1)  # 0.6 * 20 = 12 exactly


def test_decimal_kanal_to_sarsahi_full_pipeline():
    # 10.55 Kanal = 10 Kanal 11 Marla = (10*20+11)*9 = 1899 sarsahi
    total = decimal_kanal_to_sarsahi("10.55")
    assert total == Fraction(1899, 1)


# TEST 9: decimal Marla -> exact Marla + Sarsahi fraction, never rounded away.
def test_decimal_marla_11_5_gives_exact_half_sarsahi_remainder():
    marla, sarsahi = decimal_marla_to_marla_sarsahi("11.5")
    assert marla == 11
    assert sarsahi == Fraction(9, 2)  # 0.5 * 9 = 4.5 exactly, not rounded


def test_decimal_marla_conversion_rejects_negative():
    import pytest
    with pytest.raises(ValueError):
        decimal_marla_to_marla_sarsahi("-1")
