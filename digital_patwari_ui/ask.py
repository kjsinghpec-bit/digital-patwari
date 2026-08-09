"""The "Ask Digital Patwari" adapter boundary.

Design constraint: this feature must never generate prose. Every answer is
produced by a real method on ``digital_patwari.query.FardQueryEngine``,
reading only the reconciled canonical record for the document the citizen
uploaded. There is no free-text generation anywhere in this module.

That leaves one genuine problem: mapping a citizen's typed sentence to a
method. It is solved conservatively — a small, explicit, deterministic
router. When the router is not confident, the honest ``unsupported`` state
is returned with the questions that *can* be answered. It never guesses at
an intent, and it never answers a question it did not recognise.

``AskAdapter`` is a Protocol so a different question-answering backend can
be substituted later without any other part of the UI changing.
``UnavailableAskAdapter`` is the transparent state for when no such backend
is wired up.
"""
from __future__ import annotations

import re
from typing import Literal, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field

from digital_patwari.models import RemarkTarget
from digital_patwari.query import Answer, FardQueryEngine
from digital_patwari.reconciliation import ReconciledFardRecord
from digital_patwari_ui.absence import absence_claim
from digital_patwari_ui.viewmodels import COLUMN_LABELS, EvidenceIndex, EvidenceVM

AskState = Literal["answered", "unsupported", "unavailable", "no_document"]

DISCLAIMER = (
    "This describes what the uploaded record says. It is not a legal ruling on ownership "
    "and does not replace verification by the Revenue Department."
)


class AskRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question: str = Field(min_length=1, max_length=500)
    #: When the citizen taps a suggested question, the UI sends the intent
    #: directly and the text router is bypassed entirely.
    intent: str | None = None
    subject: str | None = None


class SuggestedQuestionVM(BaseModel):
    model_config = ConfigDict(extra="forbid")
    intent: str
    subject: str | None = None
    text: str


class AskAnswerVM(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question: str
    state: AskState
    #: The four claim types are kept apart on purpose. A UI must not be able
    #: to merge "what the record says" with "what we worked out".
    record_says: str | None = None
    calculated: str | None = None
    interpretation: str | None = None
    mutation_effect: str | None = None
    derived_position: str | None = None
    possession_position: str | None = None
    citations: list[EvidenceVM] = Field(default_factory=list)
    uncertain: bool = False
    uncertainty_reason: str | None = None
    message: str | None = None
    suggestions: list[SuggestedQuestionVM] = Field(default_factory=list)
    disclaimer: str = DISCLAIMER


@runtime_checkable
class AskAdapter(Protocol):
    """Any document-scoped question-answering backend."""

    available: bool

    def suggestions(self) -> list[SuggestedQuestionVM]: ...

    def ask(self, request: AskRequest) -> AskAnswerVM: ...


class UnavailableAskAdapter:
    """Honest empty state. Answers nothing, claims nothing."""

    available = False

    def __init__(self, reason: str) -> None:
        self.reason = reason

    def suggestions(self) -> list[SuggestedQuestionVM]:
        return []

    def ask(self, request: AskRequest) -> AskAnswerVM:
        return AskAnswerVM(
            question=request.question,
            state="unavailable",
            message=self.reason,
        )


# =====================================================================
# INTENT ROUTING
# =====================================================================

#: intent -> the keyword groups that must ALL appear for a text match.
#: Every group is a list of alternatives. This is deliberately small and
#: literal; an unmatched question is a supported outcome, not a failure.
_INTENT_KEYWORDS: dict[str, list[list[str]]] = {
    "pages_missing": [["page", "pages", "safa", "ਸਫ਼ਾ"], ["missing", "all", "complete", "how many"]],
    "mortgage": [["mortgage", "rehin", "rahin", "loan", "charge", "ਰਹਿਨ"]],
    "remarks": [["remark", "remarks", "column 8", "kaifiyat", "kathan", "ਕਥਨ"]],
    "mutations": [["mutation", "mutations", "inteqal", "intkal", "ਇੰਤਕਾਲ"]],
    "possession": [["possession", "girdawari", "cultivat", "farms", "tenant", "muzara", "ਕਾਸ਼ਤ"]],
    "calculation": [["calculat", "worked out", "working", "show how", "how did"]],
    "total_area": [["total", "how much", "altogether"], ["area", "land", "rakba", "ਰਕਬਾ"]],
    "owner_land": [["land", "area", "share", "hissa", "rakba", "own", "owns"]],
    "list_owners": [["who", "owner", "owners", "malkan", "ਮਾਲਕਾਨ"]],
    "khataunis_of_khewat": [["khatauni", "khataunis", "ਖਤੌਨੀ"]],
    "explain": [["explain", "summary", "summarise", "summarize", "overview", "simple"]],
}

#: Order matters: the first intent whose keyword groups all match wins.
_INTENT_ORDER = [
    "pages_missing",
    "mortgage",
    "remarks",
    "mutations",
    "possession",
    "khataunis_of_khewat",
    "calculation",
    "total_area",
    "list_owners",
    "owner_land",
    "explain",
]

_KHEWAT_NUMBER = re.compile(r"\b(\d+(?:\s*/\s*\d+)?)\b")


class QueryEngineAskAdapter:
    """Routes recognised questions to ``FardQueryEngine`` and nothing else."""

    available = True

    def __init__(
        self,
        record: ReconciledFardRecord,
        index: EvidenceIndex,
        *,
        unread_pages: list[int] | None = None,
    ) -> None:
        self.record = record
        self.index = index
        self.engine = FardQueryEngine(record)
        #: Pages that failed to read or were referenced but never
        #: uploaded. Every "nothing found" answer must consult this via
        #: digital_patwari_ui.absence.absence_claim rather than claiming
        #: absence with confidence -- see CLAUDE.md's "Missing or failed
        #: pages must never be treated as proof that data is absent."
        self.unread_pages = unread_pages or []

    # -- suggestions ----------------------------------------------------

    def suggestions(self) -> list[SuggestedQuestionVM]:
        document = self.record.document
        items: list[SuggestedQuestionVM] = [
            SuggestedQuestionVM(intent="explain", text="Explain this record in simple language"),
            SuggestedQuestionVM(intent="list_owners", text="Who is recorded as an owner?"),
        ]
        for khewat in document.khewats:
            for owner in khewat.owners:
                name = owner.normalized_owner_name or owner.raw_owner_name_parentage
                items.append(SuggestedQuestionVM(
                    intent="owner_land", subject=name,
                    text=f"What land is recorded in {name}'s name?",
                ))
                break  # one owner per Khewat keeps the list short
        for khewat in document.khewats:
            if khewat.khewat_number:
                items.append(SuggestedQuestionVM(
                    intent="khataunis_of_khewat", subject=khewat.khewat_number,
                    text=f"Which Khataunis belong to Khewat {khewat.khewat_number}?",
                ))
        items.append(SuggestedQuestionVM(intent="total_area", text="How much land is recorded in total?"))
        items.append(SuggestedQuestionVM(intent="calculation", text="Show how this area was calculated"))
        items.append(SuggestedQuestionVM(intent="pages_missing", text="Are any pages missing?"))
        if document.mutations:
            items.append(SuggestedQuestionVM(intent="mutations", text="What mutations are recorded?"))
        items.append(SuggestedQuestionVM(intent="mortgage", text="Are there any mortgages or important remarks?"))
        return items

    # -- routing --------------------------------------------------------

    def _owner_names(self) -> list[str]:
        names: list[str] = []
        for khewat in self.record.document.khewats:
            for owner in khewat.owners:
                names.append(owner.raw_owner_name_parentage)
                if owner.normalized_owner_name:
                    names.append(owner.normalized_owner_name)
        return names

    def _subject_in_text(self, text: str) -> str | None:
        """Find a name from THIS document inside the question. Only names
        the record already contains can ever be a subject."""
        lowered = text.lower()
        best: str | None = None
        for name in self._owner_names():
            candidate = name.lower()
            if candidate and candidate in lowered:
                if best is None or len(candidate) > len(best):
                    best = name
            else:
                # also match on a leading given name, e.g. "Kartar Singh"
                head = " ".join(candidate.split()[:2])
                if len(head) > 4 and head in lowered and (best is None or len(head) > len(best)):
                    best = name
        return best

    def route(self, text: str) -> tuple[str | None, str | None]:
        """Return (intent, subject). ``(None, None)`` means not recognised."""
        lowered = text.lower().strip()
        if not lowered:
            return None, None
        subject = self._subject_in_text(lowered)
        for intent in _INTENT_ORDER:
            groups = _INTENT_KEYWORDS[intent]
            if all(any(token in lowered for token in group) for group in groups):
                if intent == "owner_land" and subject is None:
                    continue
                if intent == "khataunis_of_khewat":
                    match = _KHEWAT_NUMBER.search(text)
                    return intent, match.group(1).replace(" ", "") if match else None
                return intent, subject
        if subject is not None:
            # A name from this record with no other recognised keyword is
            # answered as "what is recorded for this person".
            return "owner_land", subject
        return None, None

    # -- answering ------------------------------------------------------

    def ask(self, request: AskRequest) -> AskAnswerVM:
        intent = request.intent
        subject = request.subject
        if intent is None:
            intent, subject = self.route(request.question)
        if intent is None:
            return AskAnswerVM(
                question=request.question,
                state="unsupported",
                message=(
                    "This question was not understood. Digital Patwari answers only from the "
                    "record you uploaded, and only questions it recognises — it will not guess. "
                    "Try one of these:"
                ),
                suggestions=self.suggestions()[:6],
            )

        handler = getattr(self, f"_answer_{intent}", None)
        if handler is None:
            return AskAnswerVM(
                question=request.question,
                state="unsupported",
                message=f"'{intent}' is not a question Digital Patwari can answer.",
                suggestions=self.suggestions()[:6],
            )
        answer = handler(subject)
        if isinstance(answer, AskAnswerVM):
            return answer
        return self._from_answer(request.question, answer)

    def _from_answer(self, question: str, answer: Answer) -> AskAnswerVM:
        citations: list[EvidenceVM] = []
        for source in answer.evidence:
            citations.extend(self.index.evidence(source))
        return AskAnswerVM(
            question=question,
            state="answered",
            record_says=answer.record_says,
            calculated=answer.calculated,
            interpretation=answer.interpretation,
            mutation_effect=answer.mutation_effect,
            derived_position=answer.derived_position,
            possession_position=answer.possession_position,
            citations=citations,
            uncertain=answer.uncertain,
            uncertainty_reason=answer.uncertainty_reason,
        )

    # -- handlers (each one delegates; none of them composes prose) -----

    def _answer_explain(self, subject: str | None) -> Answer:
        return self.engine.explain_fard_simple_english()

    def _answer_list_owners(self, subject: str | None) -> Answer:
        return self.engine.list_owners()

    def _answer_total_area(self, subject: str | None) -> Answer:
        return self.engine.total_area()

    def _answer_owner_land(self, subject: str | None) -> Answer | AskAnswerVM:
        if not subject:
            return self._needs_subject("Which person's land would you like to see?")
        return self.engine.owner_land(subject)

    def _answer_mutations(self, subject: str | None) -> Answer | AskAnswerVM:
        if subject:
            return self.engine.mutations_for(subject)
        document = self.record.document
        if not document.mutations:
            claim = absence_claim("mutation entries", self.unread_pages)
            return Answer(
                question="What mutations are recorded?",
                record_says=claim.text,
                calculated=None,
                interpretation=None,
                uncertain=claim.uncertain,
                uncertainty_reason=(
                    "Some pages could not be read, so this does not confirm there are no mutations."
                    if claim.uncertain else None
                ),
            )
        lines = [
            f"[{m.status.value}] {m.raw_text}"
            + (f" (meaning: {m.parsed_meaning})" if m.parsed_meaning else "")
            for m in document.mutations
        ]
        return Answer(
            question="What mutations are recorded?",
            record_says="\n".join(lines),
            calculated=None,
            interpretation=(
                "Only a sanctioned mutation can change recorded ownership. "
                "Entries that are merely entered, presented or pending do not."
            ),
            evidence=[m.source for m in document.mutations if m.source],
            uncertain=any(m.status.value == "Uncertain" for m in document.mutations),
        )

    def _answer_calculation(self, subject: str | None) -> Answer | AskAnswerVM:
        """Show a figure together with a pointer to its full working.

        The step-by-step working itself lives on the Calculations screen,
        built from the same functions the validation gates use — this does
        not restate it in prose.
        """
        answer = self.engine.owner_land(subject) if subject else self.engine.total_area()
        pointer = "The full step-by-step working is on the 'Calculations' screen."
        return Answer(
            question=answer.question,
            record_says=answer.record_says,
            calculated=answer.calculated,
            interpretation=f"{answer.interpretation}\n\n{pointer}" if answer.interpretation else pointer,
            evidence=answer.evidence,
            confidence=answer.confidence,
            uncertain=answer.uncertain,
            uncertainty_reason=answer.uncertainty_reason,
        )

    def _answer_mortgage(self, subject: str | None) -> Answer | AskAnswerVM:
        document = self.record.document
        if not document.khewats:
            return self._no_data("There are no Khewats in the pages that were read.")
        labelled: list[Answer] = []
        for khewat in document.khewats:
            answer = self.engine.mortgage_status_for(RemarkTarget.KHEWAT, khewat.khewat_id)
            label = f"Khewat {khewat.khewat_number or '(number not read)'}"
            labelled.append(Answer(
                question=answer.question,
                record_says=f"{label}: {answer.record_says}",
                calculated=answer.calculated,
                interpretation=answer.interpretation,
                evidence=answer.evidence,
                uncertain=answer.uncertain,
                uncertainty_reason=answer.uncertainty_reason,
            ))
        # When at least one Khewat has an entry, the "nothing here" lines for
        # the others are noise; keep them only when there is nothing to report.
        with_entries = [a for a in labelled if "No mortgage (Rehin) entry is recorded" not in a.record_says]
        if with_entries:
            return self._combine("Are there any mortgages or important remarks?", with_entries)
        # Nothing recorded against any Khewat that was actually read -- the
        # per-Khewat canonical answers are all "no mortgage" boilerplate;
        # replace them with ONE centrally-worded claim that also carries
        # the partial-document uncertainty the per-Khewat answers can't see.
        claim = absence_claim("mortgage entries", self.unread_pages)
        return Answer(
            question="Are there any mortgages or important remarks?",
            record_says=claim.text,
            calculated=None,
            interpretation=None,
            evidence=[source for a in labelled for source in a.evidence],
            uncertain=claim.uncertain,
            uncertainty_reason=(
                "Some pages could not be read, so this does not confirm there is no mortgage."
                if claim.uncertain else None
            ),
        )

    def _answer_remarks(self, subject: str | None) -> Answer | AskAnswerVM:
        document = self.record.document
        if not document.remarks:
            claim = absence_claim("Column 8 remarks", self.unread_pages)
            return Answer(
                question="What is written in the remarks column?",
                record_says=claim.text,
                calculated=None, interpretation=None, uncertain=claim.uncertain,
                uncertainty_reason=(
                    "Some pages could not be read, so this does not confirm there are no remarks."
                    if claim.uncertain else None
                ),
            )
        answers = [
            self.engine.remarks_for(khewat_target, target_id)
            for khewat_target, target_id in {
                (remark.target_type, remark.target_id) for remark in document.remarks
            }
        ]
        return self._combine("What is written in the remarks column?", answers)

    def _answer_possession(self, subject: str | None) -> Answer | AskAnswerVM:
        if subject:
            return self.engine.cultivation_position_for(subject)
        document = self.record.document
        if not document.cultivation_interests:
            claim = absence_claim("cultivation or possession entries", self.unread_pages)
            return Answer(
                question="Who is recorded as cultivating this land?",
                record_says=claim.text,
                calculated=None, interpretation=None, uncertain=claim.uncertain,
                uncertainty_reason=(
                    "Some pages could not be read, so this does not confirm there are no "
                    "cultivation or possession entries."
                    if claim.uncertain else None
                ),
            )
        lines = [
            f"{interest.person_name}: {interest.relationship.value} "
            f"({interest.raw_relationship_text or 'no raw text recorded'})"
            for interest in document.cultivation_interests
        ]
        return Answer(
            question="Who is recorded as cultivating this land?",
            record_says="\n".join(lines),
            calculated=None,
            interpretation=(
                "Cultivation and possession are recorded separately from ownership. "
                "The person farming the land is not necessarily its owner."
            ),
            evidence=[i.source for i in document.cultivation_interests if i.source],
            uncertain=False,
        )

    def _answer_khataunis_of_khewat(self, subject: str | None) -> Answer | AskAnswerVM:
        document = self.record.document
        if not subject:
            return self._needs_subject("Which Khewat number would you like to see?")
        wanted = subject.replace(" ", "")
        for khewat in document.khewats:
            if khewat.khewat_number and khewat.khewat_number.replace(" ", "") == wanted:
                if not khewat.khataunis:
                    return Answer(
                        question=f"Which Khataunis belong to Khewat {khewat.khewat_number}?",
                        record_says="No Khataunis were found under this Khewat in the pages that were read.",
                        calculated=None, interpretation=None, uncertain=True,
                        uncertainty_reason="A Khewat with no Khataunis in the read pages may simply continue on a page that was not read.",
                    )
                lines = [
                    f"Khatauni {khatauni.khatauni_number} — {len(khatauni.khasras)} parcel(s)"
                    for khatauni in khewat.khataunis
                ]
                return Answer(
                    question=f"Which Khataunis belong to Khewat {khewat.khewat_number}?",
                    record_says="\n".join(lines),
                    calculated=None,
                    interpretation=(
                        "A Khewat is the ownership account; a Khatauni under it is a "
                        "cultivation/possession account. They are different numbers."
                    ),
                    evidence=[khatauni.source for khatauni in khewat.khataunis if khatauni.source],
                    uncertain=False,
                )
        return self._no_data(
            f"Khewat {subject} was not found in the pages that were read. "
            "If some pages could not be read, it may appear on one of those."
        )

    def _answer_pages_missing(self, subject: str | None) -> Answer | AskAnswerVM:
        gate = next((g for g in self.record.validation_report.gates if g.gate_id == "AG-04"), None)
        if gate is None:
            return self._no_data("The page-completeness check did not run for this document.")
        if gate.checked_entities == 0 and gate.skipped_entities:
            return Answer(
                question="Are any pages missing?",
                record_says=(
                    "This document does not print its own page total (such as \"Page 5 of 8\"), "
                    "so we cannot tell whether every page is present."
                ),
                calculated=None,
                interpretation="Absence of a stated total is not evidence that the upload is complete.",
                uncertain=True,
                uncertainty_reason="No page total is stated anywhere in the pages that were read.",
            )
        if gate.passed and not gate.issues:
            return Answer(
                question="Are any pages missing?",
                record_says="Every page the document says it has is present.",
                calculated=None, interpretation=None, uncertain=False,
            )
        return Answer(
            question="Are any pages missing?",
            record_says="\n".join(issue.message for issue in gate.issues),
            calculated=None,
            interpretation="Missing pages are unknown content, not empty content.",
            uncertain=True,
            uncertainty_reason="The document is incomplete.",
        )

    # -- helpers --------------------------------------------------------

    def _combine(self, question: str, answers: list[Answer]) -> Answer:
        """Concatenate several engine answers without rewriting any of them."""
        return Answer(
            question=question,
            record_says="\n\n".join(a.record_says for a in answers if a.record_says),
            calculated=None,
            interpretation="\n\n".join(a.interpretation for a in answers if a.interpretation) or None,
            evidence=[source for a in answers for source in a.evidence],
            uncertain=any(a.uncertain for a in answers),
            uncertainty_reason=next((a.uncertainty_reason for a in answers if a.uncertainty_reason), None),
        )

    def _needs_subject(self, message: str) -> AskAnswerVM:
        return AskAnswerVM(
            question=message,
            state="unsupported",
            message=message,
            suggestions=self.suggestions()[:6],
        )

    def _no_data(self, message: str) -> AskAnswerVM:
        return AskAnswerVM(
            question=message,
            state="unsupported",
            message=message,
            suggestions=self.suggestions()[:6],
        )


def build_ask_adapter(
    record: ReconciledFardRecord | None,
    index: EvidenceIndex | None,
    *,
    unread_pages: list[int] | None = None,
) -> AskAdapter:
    if record is None or index is None:
        return UnavailableAskAdapter(
            "There is no readable record to ask questions about yet. Upload a Fard, or "
            "retry the pages that could not be processed."
        )
    return QueryEngineAskAdapter(record, index, unread_pages=unread_pages)


__all__ = [
    "AskAdapter",
    "AskAnswerVM",
    "AskRequest",
    "QueryEngineAskAdapter",
    "SuggestedQuestionVM",
    "UnavailableAskAdapter",
    "build_ask_adapter",
    "COLUMN_LABELS",
]
