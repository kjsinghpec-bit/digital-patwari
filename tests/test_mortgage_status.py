"""TEST 10-13: mutation status granularity (referenced/pending vs.
sanctioned) and mortgage active-vs-discharged resolution. A mutation
NUMBER being present must never be read as automatic approval, and a
mortgage MENTION must never be read as an automatically active loan."""
from patwari_agent import (
    ExtractionStatus,
    MortgageStatus,
    MutationStatus,
    MutationType,
    RemarkTarget,
    resolve_mortgage_status,
)
from tests.factories import make_document, make_khewat, make_mutation


# TEST 10: mutation referenced but not sanctioned.
def test_pending_mutation_is_not_treated_as_sanctioned():
    khewat = make_khewat("KHW-1")
    mutation = make_mutation("MUT-1", RemarkTarget.KHEWAT, "KHW-1", MutationStatus.PENDING,
                              raw_text="Mutation No. 500 entered, pending verification.")
    document = make_document(khewats=[khewat], mutations=[mutation])
    assert document.mutations[0].status == MutationStatus.PENDING


# TEST 11: mutation sanctioned.
def test_approved_mutation_status_is_distinct_and_explicit():
    khewat = make_khewat("KHW-1")
    mutation = make_mutation("MUT-1", RemarkTarget.KHEWAT, "KHW-1", MutationStatus.APPROVED,
                              raw_text="Mutation No. 501, sanctioned.")
    document = make_document(khewats=[khewat], mutations=[mutation])
    assert document.mutations[0].status == MutationStatus.APPROVED


def test_rejected_and_uncertain_statuses_are_representable():
    khewat = make_khewat("KHW-1")
    rejected = make_mutation("MUT-R", RemarkTarget.KHEWAT, "KHW-1", MutationStatus.REJECTED,
                              raw_text="Mutation No. 502, rejected.")
    uncertain = make_mutation("MUT-U", RemarkTarget.KHEWAT, "KHW-1", MutationStatus.UNCERTAIN,
                               raw_text="Mutation number partly illegible.",
                               extraction_status=ExtractionStatus.UNCERTAIN)
    document = make_document(khewats=[khewat], mutations=[rejected, uncertain])
    assert document.mutations[0].status == MutationStatus.REJECTED
    assert document.mutations[1].status == MutationStatus.UNCERTAIN


# TEST 12: active mortgage entry (no matching discharge found).
def test_mortgage_with_no_discharge_is_likely_active_not_confirmed():
    khewat = make_khewat("KHW-1")
    mortgage = make_mutation(
        "MUT-MORT", RemarkTarget.KHEWAT, "KHW-1", MutationStatus.APPROVED,
        mutation_type=MutationType.MORTGAGE,
        raw_text="Mortgaged to Bank X for Rs. 500,000.",
    )
    document = make_document(khewats=[khewat], mutations=[mortgage])
    finding = resolve_mortgage_status(document, RemarkTarget.KHEWAT, "KHW-1")
    assert finding.status == MortgageStatus.ACTIVE_MORTGAGE_LIKELY
    assert "confirm" in finding.note.lower() or "likely" in finding.note.lower()


# TEST 13: mortgage discharge/release entry cancels the active status.
def test_mortgage_with_matching_discharge_is_not_active():
    khewat = make_khewat("KHW-1")
    mortgage = make_mutation(
        "MUT-MORT", RemarkTarget.KHEWAT, "KHW-1", MutationStatus.APPROVED,
        mutation_type=MutationType.MORTGAGE,
        raw_text="Mortgaged to Bank X for Rs. 500,000.",
    )
    discharge = make_mutation(
        "MUT-DISCHARGE", RemarkTarget.KHEWAT, "KHW-1", MutationStatus.APPROVED,
        mutation_type=MutationType.RELEASE_DISCHARGE,
        discharges_mutation_id="MUT-MORT",
        raw_text="Mortgage released/discharged, loan repaid.",
    )
    document = make_document(khewats=[khewat], mutations=[mortgage, discharge])
    finding = resolve_mortgage_status(document, RemarkTarget.KHEWAT, "KHW-1")
    assert finding.status == MortgageStatus.DISCHARGED


def test_no_mortgage_entry_detected_when_none_recorded():
    khewat = make_khewat("KHW-1")
    document = make_document(khewats=[khewat])
    finding = resolve_mortgage_status(document, RemarkTarget.KHEWAT, "KHW-1")
    assert finding.status == MortgageStatus.NO_MORTGAGE_DETECTED


def test_mortgage_status_via_query_engine_flags_uncertain_for_active():
    from patwari_agent import FardQueryEngine, reconcile, run_axiom_gates

    khewat = make_khewat("KHW-1")
    mortgage = make_mutation(
        "MUT-MORT", RemarkTarget.KHEWAT, "KHW-1", MutationStatus.APPROVED,
        mutation_type=MutationType.MORTGAGE, raw_text="Mortgaged to Bank X.",
    )
    document = make_document(khewats=[khewat], mutations=[mortgage])
    engine = FardQueryEngine(reconcile(document, run_axiom_gates(document)))
    answer = engine.mortgage_status_for(RemarkTarget.KHEWAT, "KHW-1")
    assert answer.uncertain
    assert "active_mortgage_likely" in answer.interpretation.lower()
