"""Punjab revenue terminology dictionary.

Every entry carries its own validation status. Terms learned from
instructional video transcripts are NOT automatically authoritative:
auto-generated Punjabi captions corrupt Urdu/Persian revenue vocabulary,
fractions and numbers routinely. So each term records how well established
it is, and callers can refuse to rely on anything not CONFIRMED.

A term's meaning never establishes a legal conclusion by itself. Knowing
that "mushtari" means purchaser tells you a role, NOT the scope of what was
purchased -- that must come from the named Khasras, the mutation, and the
surrounding record.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class TermValidation(str, Enum):
    """How much weight a term's normalization may carry."""
    CONFIRMED_DOMAIN_RULE = "confirmed_domain_rule"
    NEW_GENERAL_READING_RULE = "new_general_reading_rule"
    USEFUL_HEURISTIC = "useful_heuristic"
    NEEDS_EXPERT_VALIDATION = "needs_expert_validation"
    NEEDS_LEGAL_OR_MANUAL_VALIDATION = "needs_legal_or_manual_validation"
    TRANSCRIPT_ERROR_OR_UNRELIABLE = "transcript_error_or_unreliable"


class TermCategory(str, Enum):
    PARTY_ROLE = "party_role"
    IRRIGATION = "irrigation"
    LAND_CLASSIFICATION = "land_classification"
    CULTIVATION = "cultivation"
    STRUCTURE = "structure"
    TRANSACTION = "transaction"
    COUNT = "count"


@dataclass(frozen=True)
class RevenueTerm:
    raw_term: str                    # as it may appear (transliterated)
    normalized: str                  # canonical form used internally
    meaning: str                     # plain-English meaning
    category: TermCategory
    validation: TermValidation
    variants: tuple[str, ...] = ()   # spelling variants incl. likely caption corruptions
    caution: str | None = None       # what this term does NOT establish


#: Deliberately conservative. Only terms whose *meaning* is well established
#: are marked CONFIRMED; anything whose spelling or scope came primarily from
#: an auto-captioned video stays at a lower validation level.
REVENUE_TERMS: tuple[RevenueTerm, ...] = (
    RevenueTerm(
        raw_term="Mushtari", normalized="mushtari", meaning="purchaser / buyer",
        category=TermCategory.PARTY_ROLE, validation=TermValidation.CONFIRMED_DOMAIN_RULE,
        variants=("mushtri", "mushtary", "mustari"),
        caution=(
            "Establishes purchaser status ONLY. It does not establish that the person owns the "
            "whole Khewat, nor the scope of the purchase -- scope must come from named Khasras, "
            "the mutation entry and surrounding record."
        ),
    ),
    RevenueTerm(
        raw_term="Mushtariyan", normalized="mushtari", meaning="purchasers / buyers (plural)",
        category=TermCategory.PARTY_ROLE, validation=TermValidation.CONFIRMED_DOMAIN_RULE,
        variants=("mushtarian", "mushtriyan"),
        caution="Plural of mushtari; same scope caution applies.",
    ),
    RevenueTerm(
        raw_term="Baya", normalized="baya", meaning="seller / transferor",
        category=TermCategory.PARTY_ROLE, validation=TermValidation.NEEDS_EXPERT_VALIDATION,
        variants=("bai", "bay", "baye"),
        caution=(
            "Transliteration observed in an auto-captioned source and not independently confirmed; "
            "treat the spelling as provisional and preserve the original text as evidence."
        ),
    ),
    RevenueTerm(
        raw_term="Khud Kasht", normalized="khud_kasht", meaning="self-cultivation by the owner",
        category=TermCategory.CULTIVATION, validation=TermValidation.CONFIRMED_DOMAIN_RULE,
        variants=("khudkasht", "khud-kasht", "khudkast"),
        caution=(
            "Evidence that the owner is ALSO recorded as cultivating. Absence of this marking is "
            "not evidence of the opposite, and ownership alone never implies Khud Kasht."
        ),
    ),
    RevenueTerm(
        raw_term="Muzara", normalized="muzara", meaning="tenant / cultivator who is not the owner",
        category=TermCategory.CULTIVATION, validation=TermValidation.CONFIRMED_DOMAIN_RULE,
        variants=("mazara", "muzaara"),
        caution="A tenant cultivating land is not thereby an owner of it.",
    ),
    RevenueTerm(
        raw_term="Maqbuza Malkan", normalized="maqbuza_malkan", meaning="in the possession of the owners",
        category=TermCategory.CULTIVATION, validation=TermValidation.USEFUL_HEURISTIC,
        variants=("makbuja malkan", "maqbooza malkan"),
    ),
    RevenueTerm(
        raw_term="Chahi", normalized="chahi", meaning="well-irrigated land",
        category=TermCategory.IRRIGATION, validation=TermValidation.CONFIRMED_DOMAIN_RULE,
        variants=("chaahi",),
    ),
    RevenueTerm(
        raw_term="Nehri", normalized="nehri", meaning="canal-irrigated land",
        category=TermCategory.IRRIGATION, validation=TermValidation.CONFIRMED_DOMAIN_RULE,
        variants=("nahri", "nehari"),
    ),
    RevenueTerm(
        raw_term="Barani", normalized="barani", meaning="rain-fed land",
        category=TermCategory.IRRIGATION, validation=TermValidation.CONFIRMED_DOMAIN_RULE,
        variants=("baraani",),
    ),
    RevenueTerm(
        raw_term="Mazru'a", normalized="mazrua", meaning="cultivated land",
        category=TermCategory.LAND_CLASSIFICATION, validation=TermValidation.NEEDS_EXPERT_VALIDATION,
        variants=("majrua", "mazrua", "majru'a"),
        caution="Spelling observed via auto-caption; meaning is broadly established but preserve raw text.",
    ),
    RevenueTerm(
        raw_term="Gair Mazru'a", normalized="gair_mazrua", meaning="uncultivated land",
        category=TermCategory.LAND_CLASSIFICATION, validation=TermValidation.NEEDS_EXPERT_VALIDATION,
        variants=("gair majrua", "ghair mazrua"),
    ),
    RevenueTerm(
        raw_term="Gair Mumkin", normalized="gair_mumkin", meaning="land not capable of cultivation",
        category=TermCategory.LAND_CLASSIFICATION, validation=TermValidation.CONFIRMED_DOMAIN_RULE,
        variants=("ghair mumkin", "gairmumkin"),
    ),
    RevenueTerm(
        raw_term="Kita", normalized="kita", meaning="a count of Khasra numbers / parcels",
        category=TermCategory.COUNT, validation=TermValidation.NEW_GENERAL_READING_RULE,
        variants=("kite", "kitta", "kitte"),
        caution=(
            "A COUNT, never an area. 'Kita 3' indicates three parcels, not three of any land unit. "
            "Never treat a Kita value as Kanal/Marla/Sarsahi."
        ),
    ),
    RevenueTerm(
        raw_term="Inteqal", normalized="inteqal", meaning="mutation (a revenue transaction entry)",
        category=TermCategory.TRANSACTION, validation=TermValidation.CONFIRMED_DOMAIN_RULE,
        variants=("intqal", "intkal", "intiqal"),
        caution="Presence of a mutation number is not evidence that the mutation was sanctioned.",
    ),
    RevenueTerm(
        raw_term="Rehin", normalized="rehin", meaning="mortgage",
        category=TermCategory.TRANSACTION, validation=TermValidation.CONFIRMED_DOMAIN_RULE,
        variants=("rahin", "rehan"),
        caution="A mortgage mention is not evidence the mortgage is still active; look for a discharge.",
    ),
    RevenueTerm(
        raw_term="Vishesh Kathan", normalized="vishesh_kathan", meaning="special remarks column (Column 8)",
        category=TermCategory.STRUCTURE, validation=TermValidation.CONFIRMED_DOMAIN_RULE,
        variants=("khana kaifiyat", "vishesh kathn"),
    ),
    RevenueTerm(
        raw_term="Murabba", normalized="murabba", meaning="a larger mapped land grouping containing Khasras",
        category=TermCategory.STRUCTURE, validation=TermValidation.CONFIRMED_DOMAIN_RULE,
        caution=(
            "Kept strictly separate from Khasra number. No assumption is made about a Murabba's "
            "size or parcel count -- that was not independently verified."
        ),
    ),
)

#: Built in priority order so a broader entry never shadows a more specific
#: one. Several terms share a normalized form on purpose (Mushtari and
#: Mushtariyan both normalize to "mushtari"), so exact raw_term spellings are
#: registered FIRST and later passes use setdefault -- otherwise the plural
#: would overwrite the singular's own caution text.
_LOOKUP: dict[str, RevenueTerm] = {}
for _term in REVENUE_TERMS:
    _LOOKUP[_term.raw_term.strip().lower()] = _term
for _term in REVENUE_TERMS:
    _LOOKUP.setdefault(_term.normalized.strip().lower(), _term)
for _term in REVENUE_TERMS:
    for _variant in _term.variants:
        _LOOKUP.setdefault(_variant.strip().lower(), _term)


def lookup_term(text: str) -> RevenueTerm | None:
    """Exact-ish lookup of a single revenue term. Returns None rather than
    guessing at an unrecognized word."""
    if not text:
        return None
    return _LOOKUP.get(text.strip().lower())


def find_terms(text: str) -> list[RevenueTerm]:
    """Find known revenue terms mentioned anywhere in a passage.

    Substring matching on a known vocabulary -- it never invents a term or
    normalizes an unrecognized word."""
    if not text:
        return []
    haystack = text.lower()
    found: list[RevenueTerm] = []
    for term in REVENUE_TERMS:
        candidates = (term.raw_term, term.normalized.replace("_", " "), *term.variants)
        if any(candidate.lower() in haystack for candidate in candidates):
            if term not in found:
                found.append(term)
    return found


def is_reliable(term: RevenueTerm) -> bool:
    """Whether a term's normalization is established enough to rely on
    without flagging it for human confirmation."""
    return term.validation in (
        TermValidation.CONFIRMED_DOMAIN_RULE,
        TermValidation.NEW_GENERAL_READING_RULE,
    )
