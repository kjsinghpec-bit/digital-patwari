"""Centralized page-completeness and absence-claim policy.

CLAUDE.md: "Missing or failed pages must never be treated as proof that
data is absent." This module is the ONLY place that:

  1. decides which pages are "unread" (failed, or referenced by a stated
     total but never uploaded at all), and
  2. composes the wording and uncertainty state for a "nothing found"
     claim over a partial vs. complete document.

``ask.py``, ``viewmodels.py`` and the JavaScript screens must all consume
the result of ``absence_claim`` rather than writing their own "No X found"
text, so the policy can never drift between the citizen-chat answers, the
typed view models, and the rendered screens. The JS side receives the
already-composed text/tone/uncertain fields on the document view model
and renders them verbatim -- it never re-derives them.

This module depends only on canonical, read-only helpers
(``digital_patwari.extraction``, ``digital_patwari.validation``'s
``_all_source_references``) and has no dependency on ``viewmodels`` or
``ask``, so both of those can import it without a cycle.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from digital_patwari.extraction import ExtractionResult
from digital_patwari.models import DigitalPatwariDocument
from digital_patwari.validation import _all_source_references

Tone = Literal["ok", "unknown"]


def stated_total_pages(document: DigitalPatwariDocument | None) -> int | None:
    """The largest page total any page of the document claims for itself
    (e.g. "Page 5 of 8" -> 8). None when no page states one."""
    if document is None:
        return None
    totals = {
        source.total_pages for source in _all_source_references(document)
        if source is not None and source.total_pages is not None
    }
    return max(totals) if totals else None


def compute_unread_pages(
    result: ExtractionResult,
    uploaded_pages: tuple[int, ...],
) -> list[int]:
    """Pages whose content is UNKNOWN: uploaded but failed to read, or
    referenced by the document's own stated page total but never supplied
    at all. Either way, these pages must never be treated as evidence that
    something is absent from the document."""
    successful = set(result.successful_pages)
    failed = set(result.failed_pages)
    total = stated_total_pages(result.document)
    known = set(uploaded_pages) | successful | failed | set(range(1, (total or 0) + 1))
    return sorted(page for page in known if page not in successful)


def is_partial(unread_pages: list[int] | tuple[int, ...]) -> bool:
    return bool(unread_pages)


@dataclass(frozen=True)
class AbsenceClaim:
    """One 'nothing found' statement, with its uncertainty state attached.

    ``tone`` mirrors the rest of the UI's finding/status vocabulary:
    "ok" for a confidently-empty complete document, "unknown" for a
    partial one where absence cannot be confirmed.
    """

    text: str
    tone: Tone
    uncertain: bool


def absence_claim(noun_phrase: str, unread_pages: list[int] | tuple[int, ...]) -> AbsenceClaim:
    """Compose the one-and-only wording for "no <noun_phrase> were found",
    aware of whether any page of the document is unread.

    ``noun_phrase`` is a plural noun phrase completing "No {noun_phrase}
    were found[...]", e.g. "mutation entries", "Column 8 remarks",
    "cultivation or possession entries", "mortgage entries".
    """
    if is_partial(unread_pages):
        text = (
            f"No {noun_phrase} were found in the pages successfully read. "
            "Unread pages may contain additional information."
        )
        return AbsenceClaim(text=text, tone="unknown", uncertain=True)
    return AbsenceClaim(text=f"No {noun_phrase} were found.", tone="ok", uncertain=False)
