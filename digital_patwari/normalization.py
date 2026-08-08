from __future__ import annotations

from fractions import Fraction
from typing import Any


def normalize_optional_text(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    value = " ".join(value.split()).strip()
    return value or None


def parse_fraction(value: Any) -> str:
    if isinstance(value, dict):
        numerator = value.get("numerator")
        denominator = value.get("denominator")
        if numerator is None or denominator is None:
            raise ValueError("Fraction requires numerator and denominator.")
        fraction = Fraction(int(numerator), int(denominator))
    elif isinstance(value, Fraction):
        fraction = value
    elif isinstance(value, int):
        fraction = Fraction(value, 1)
    elif isinstance(value, float):
        fraction = Fraction(str(value))
    elif isinstance(value, str):
        cleaned = value.strip().replace(" ", "")
        if not cleaned:
            raise ValueError("Share fraction cannot be empty.")
        fraction = Fraction(cleaned)
    else:
        raise ValueError(f"Unsupported fraction value: {value!r}")

    if fraction < 0:
        raise ValueError("Share fraction cannot be negative.")
    return f"{fraction.numerator}/{fraction.denominator}"


def _to_exact_fraction(value: Any) -> Fraction:
    if isinstance(value, Fraction):
        return value
    if isinstance(value, int):
        return Fraction(value, 1)
    if isinstance(value, str):
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Decimal value cannot be empty.")
        return Fraction(cleaned)
    if isinstance(value, float):
        # str(value) first, not Fraction(value) directly -- avoids binary
        # floating-point noise (e.g. Fraction(10.55) != Fraction("10.55")).
        return Fraction(str(value))
    raise ValueError(f"Unsupported decimal value: {value!r}")


def decimal_kanal_to_kanal_marla(value: Any, marla_per_kanal: int = 20) -> tuple[int, Fraction]:
    """Convert a decimal-Kanal figure (e.g. "10.55 Kanal", as some Fards
    print it) into (whole_kanal, exact_marla_fraction).

    The decimal fraction of a Kanal is NOT marla digits pasted together --
    10.55 Kanal is NOT "10 Kanal 55 Marla". The fractional part of the
    Kanal figure must be multiplied by marla_per_kanal:
        10.55 Kanal = 10 Kanal + (0.55 x 20) Marla = 10 Kanal 11 Marla.
    Returns exact Fraction marla so a non-whole result (e.g. 10.551 Kanal)
    is never silently rounded away.
    """
    total = _to_exact_fraction(value)
    if total < 0:
        raise ValueError("Kanal value cannot be negative.")
    whole_kanal = int(total)
    fractional_kanal = total - whole_kanal
    marla = fractional_kanal * marla_per_kanal
    return whole_kanal, marla


def decimal_marla_to_marla_sarsahi(value: Any, sarsahi_per_marla: int = 9) -> tuple[int, Fraction]:
    """Convert a decimal-Marla figure (e.g. 11.5 Marla) into
    (whole_marla, exact_sarsahi_fraction):
        11.5 Marla = 11 Marla + (0.5 x 9) Sarsahi = 11 Marla 4.5 Sarsahi.
    """
    total = _to_exact_fraction(value)
    if total < 0:
        raise ValueError("Marla value cannot be negative.")
    whole_marla = int(total)
    fractional_marla = total - whole_marla
    sarsahi = fractional_marla * sarsahi_per_marla
    return whole_marla, sarsahi


def subtract_shares(original: Any, transferred: Any) -> str:
    """Exact share subtraction: remaining = original - transferred.

    Deterministic code, never LLM arithmetic. Raises when the transfer
    exceeds the original rather than returning a negative share -- a
    negative ownership fraction is not a real-world state, it is evidence
    that the extraction or the mutation reading is wrong, and must surface
    as an error instead of propagating silently."""
    original_fraction = Fraction(parse_fraction(original))
    transferred_fraction = Fraction(parse_fraction(transferred))
    if transferred_fraction > original_fraction:
        raise ValueError(
            f"Transferred share {transferred_fraction} exceeds original share "
            f"{original_fraction}; cannot produce a negative remaining share."
        )
    remaining = original_fraction - transferred_fraction
    return f"{remaining.numerator}/{remaining.denominator}"


def add_shares(*shares: Any) -> str:
    """Exact share addition (e.g. accumulating acquisitions)."""
    total = Fraction(0)
    for share in shares:
        total += Fraction(parse_fraction(share))
    return f"{total.numerator}/{total.denominator}"


def area_from_share(total_area_sarsahi: int, share: Any) -> Fraction:
    """Exact entitlement area = total area x share.

    IMPORTANT (Part 42): the caller must pass the ACTUAL total area of the
    correct scope. A share's denominator is NOT the total Marla count. It
    coincidentally is in some teaching examples (a 46K-14M Khewat = 934
    Marla holding shares like 404/934), and that coincidence must never be
    generalized into inferring area from a denominator -- see
    `share_denominator_matches_total_marla` for the explicit guard."""
    return Fraction(total_area_sarsahi) * Fraction(parse_fraction(share))


def raw_share_denominator(share: Any) -> int | None:
    """The denominator AS PRINTED, before reduction to lowest terms.

    `parse_fraction` canonicalizes (404/934 -> 202/467), which is correct
    for arithmetic but loses the printed denominator. Some checks need the
    printed form, so read it directly without normalizing."""
    if isinstance(share, str) and "/" in share:
        _, _, denominator_text = share.strip().replace(" ", "").partition("/")
        try:
            denominator = int(denominator_text)
        except ValueError:
            return None
        return denominator or None
    if isinstance(share, dict) and share.get("denominator") is not None:
        try:
            return int(share["denominator"]) or None
        except (TypeError, ValueError):
            return None
    return None


def share_denominator_matches_total_marla(share: Any, total_area_sarsahi: int, sarsahi_per_marla: int = 9) -> bool:
    """True when a share's PRINTED denominator happens to equal the scope's
    total Marla count.

    This exists ONLY to detect and flag the coincidence, never to exploit
    it. Some Fards do print shares whose denominator equals the total
    Marlas (a 46K-14M = 934 Marla Khewat carrying shares like 404/934),
    which tempts a reader into treating the numerator as "Marlas owned"
    directly. That shortcut is not a general rule and silently produces
    wrong answers whenever the denominators are ordinary fractions
    (1/4, 1/7, 209/944...). Digital Patwari always computes
    total_area x share instead."""
    total_marla, remainder = divmod(total_area_sarsahi, sarsahi_per_marla)
    if remainder:
        return False
    denominator = raw_share_denominator(share)
    return denominator is not None and denominator == total_marla


def decimal_kanal_to_sarsahi(value: Any, marla_per_kanal: int = 20, sarsahi_per_marla: int = 9) -> Fraction:
    """Full deterministic conversion of a decimal-Kanal figure straight to
    exact total sarsahi, composing the two conversions above rather than
    re-deriving the arithmetic -- one canonical path for this figure."""
    whole_kanal, marla_fraction = decimal_kanal_to_kanal_marla(value, marla_per_kanal)
    return Fraction(whole_kanal * marla_per_kanal * sarsahi_per_marla) + (marla_fraction * sarsahi_per_marla)
