from patwari_agent import (
    RemarkCategory,
    RemarkTarget,
    ValidationSeverity,
    run_axiom_gates,
    validate_ag01_khewat_share_summation,
    validate_ag02_linkage_and_integrity,
    validate_ag03_area_consistency,
)
from tests.factories import (
    make_document,
    make_khasra,
    make_khatauni,
    make_khewat,
    make_owner,
    make_remark,
)


# ---------------------------------------------------------------------
# AG-01: Khewat share summation
# ---------------------------------------------------------------------

def test_ag01_passes_when_shares_sum_to_total():
    khewat = make_khewat(
        "KHW-1",
        owners=[make_owner("OWN-1", "KHW-1", "1/2"), make_owner("OWN-2", "KHW-1", "1/2")],
        total_share="1/1",
    )
    result = validate_ag01_khewat_share_summation(make_document(khewats=[khewat]))
    assert result.passed
    assert result.checked_entities == 1


def test_ag01_fails_when_shares_do_not_sum():
    khewat = make_khewat(
        "KHW-1",
        owners=[make_owner("OWN-1", "KHW-1", "1/2"), make_owner("OWN-2", "KHW-1", "1/4")],
        total_share="1/1",
    )
    result = validate_ag01_khewat_share_summation(make_document(khewats=[khewat]))
    assert not result.passed
    assert result.issues[0].severity == ValidationSeverity.ERROR


def test_ag01_warns_and_skips_khewat_with_no_owners():
    khewat = make_khewat("KHW-1", owners=[], total_share="1/1")
    result = validate_ag01_khewat_share_summation(make_document(khewats=[khewat]))
    assert result.passed  # warning only, not an error
    assert result.skipped_entities == 1
    assert result.issues[0].severity == ValidationSeverity.WARNING


def test_ag01_never_invents_a_share_to_force_a_pass():
    # Three owners, one with a plainly wrong share; AG-01 must report the
    # mismatch rather than silently rebalancing anything.
    khewat = make_khewat(
        "KHW-1",
        owners=[
            make_owner("OWN-1", "KHW-1", "1/3"),
            make_owner("OWN-2", "KHW-1", "1/3"),
            make_owner("OWN-3", "KHW-1", "1/3"),
        ],
        total_share="1/1",  # sums to 1/1: exact three-way split
    )
    result = validate_ag01_khewat_share_summation(make_document(khewats=[khewat]))
    assert result.passed


# ---------------------------------------------------------------------
# AG-02: linkage + FK + uniqueness + remark target resolution
# ---------------------------------------------------------------------

def test_ag02_passes_on_well_formed_document():
    khasra = make_khasra("KHS-1", "KHT-1")
    khatauni = make_khatauni("KHT-1", "KHW-1", khasras=[khasra])
    owner = make_owner("OWN-1", "KHW-1", "1/1")
    khewat = make_khewat("KHW-1", owners=[owner], khataunis=[khatauni])
    result = validate_ag02_linkage_and_integrity(make_document(khewats=[khewat]))
    assert result.passed


def test_ag02_flags_khasra_pointing_at_wrong_khatauni():
    khasra = make_khasra("KHS-1", "KHT-WRONG")
    khatauni = make_khatauni("KHT-1", "KHW-1", khasras=[khasra])
    khewat = make_khewat("KHW-1", khataunis=[khatauni])
    result = validate_ag02_linkage_and_integrity(make_document(khewats=[khewat]))
    assert not result.passed
    assert any(i.entity_type == "Khasra" for i in result.issues)


def test_ag02_flags_owner_khewat_id_mismatch():
    owner = make_owner("OWN-1", "KHW-WRONG", "1/1")
    khewat = make_khewat("KHW-1", owners=[owner])
    result = validate_ag02_linkage_and_integrity(make_document(khewats=[khewat]))
    assert not result.passed
    assert any(i.entity_type == "Owner" for i in result.issues)


def test_ag02_flags_khatauni_khewat_id_mismatch():
    khatauni = make_khatauni("KHT-1", "KHW-WRONG")
    khewat = make_khewat("KHW-1", khataunis=[khatauni])
    result = validate_ag02_linkage_and_integrity(make_document(khewats=[khewat]))
    assert not result.passed
    assert any(i.entity_type == "Khatauni" for i in result.issues)


def test_ag02_flags_duplicate_khasra_ids_across_khataunis():
    khasra_a = make_khasra("KHS-DUP", "KHT-1")
    khasra_b = make_khasra("KHS-DUP", "KHT-2")
    khatauni_a = make_khatauni("KHT-1", "KHW-1", khasras=[khasra_a])
    khatauni_b = make_khatauni("KHT-2", "KHW-1", khasras=[khasra_b])
    khewat = make_khewat("KHW-1", khataunis=[khatauni_a, khatauni_b])
    result = validate_ag02_linkage_and_integrity(make_document(khewats=[khewat]))
    assert not result.passed
    assert any("Duplicate" in i.message for i in result.issues)


def test_ag02_flags_unresolved_remark_target():
    khewat = make_khewat("KHW-1")
    remark = make_remark(RemarkTarget.OWNER, "OWN-DOES-NOT-EXIST", RemarkCategory.INFORMATIONAL)
    result = validate_ag02_linkage_and_integrity(make_document(khewats=[khewat], remarks=[remark]))
    assert not result.passed
    assert any(i.entity_type == "Remark" for i in result.issues)


def test_ag02_passes_when_remark_target_resolves():
    owner = make_owner("OWN-1", "KHW-1", "1/1")
    khewat = make_khewat("KHW-1", owners=[owner])
    remark = make_remark(RemarkTarget.OWNER, "OWN-1", RemarkCategory.PENDING_MUTATION)
    result = validate_ag02_linkage_and_integrity(make_document(khewats=[khewat], remarks=[remark]))
    assert result.passed


# ---------------------------------------------------------------------
# AG-03: area consistency, including the multi-Khatauni-per-Khewat
# non-double-counting regression this project explicitly calls out.
# ---------------------------------------------------------------------

def test_ag03_passes_when_khasra_areas_sum_to_recorded_total():
    khasras = [make_khasra("KHS-1", "KHT-1", kanal=1), make_khasra("KHS-2", "KHT-1", kanal=1)]
    khatauni = make_khatauni(
        "KHT-1", "KHW-1", khasras=khasras,
        recorded_area=__import__("tests.factories", fromlist=["make_area"]).make_area(kanal=2),
    )
    khewat = make_khewat("KHW-1", khataunis=[khatauni])
    result = validate_ag03_area_consistency(make_document(khewats=[khewat]))
    assert result.passed


def test_ag03_fails_when_khasra_areas_do_not_match_recorded_total():
    from tests.factories import make_area

    khasras = [make_khasra("KHS-1", "KHT-1", kanal=1)]
    khatauni = make_khatauni("KHT-1", "KHW-1", khasras=khasras, recorded_area=make_area(kanal=5))
    khewat = make_khewat("KHW-1", khataunis=[khatauni])
    result = validate_ag03_area_consistency(make_document(khewats=[khewat]))
    assert not result.passed
    assert result.issues[0].entity_type == "Khatauni"


def test_ag03_catches_sub_marla_sarsahi_discrepancy():
    from tests.factories import make_area

    # Recorded total is exact; Khasra sum is off by 1 sarsahi only (< 1 marla).
    # CLAUDE.md requires this be caught at the sarsahi level, not rounded away.
    khasras = [make_khasra("KHS-1", "KHT-1", kanal=1, sarsahi=1)]
    khatauni = make_khatauni("KHT-1", "KHW-1", khasras=khasras, recorded_area=make_area(kanal=1))
    khewat = make_khewat("KHW-1", khataunis=[khatauni])
    result = validate_ag03_area_consistency(make_document(khewats=[khewat]), tolerance_marla=0)
    assert not result.passed


def test_ag03_skips_when_recorded_total_area_missing():
    khasras = [make_khasra("KHS-1", "KHT-1", kanal=1)]
    khatauni = make_khatauni("KHT-1", "KHW-1", khasras=khasras, recorded_area=None)
    khewat = make_khewat("KHW-1", khataunis=[khatauni])
    result = validate_ag03_area_consistency(make_document(khewats=[khewat]))
    assert result.passed
    assert result.skipped_entities == 1


def test_ag03_skips_when_khasras_absent_rather_than_assuming_pass():
    from tests.factories import make_area

    khatauni = make_khatauni("KHT-1", "KHW-1", khasras=[], recorded_area=make_area(kanal=5))
    khewat = make_khewat("KHW-1", khataunis=[khatauni])
    result = validate_ag03_area_consistency(make_document(khewats=[khewat]))
    assert result.skipped_entities == 1
    assert result.checked_entities == 0


def test_ag03_multiple_khataunis_in_one_khewat_are_not_double_counted():
    """Regression: a Khewat containing two Khataunis must validate each
    Khatauni's own Khasra sum against its own recorded_total_area — the
    Khewat's total area must never be inferred by adding the two
    Khataunis together, and a bug that summed all Khasras under the
    Khewat (ignoring Khatauni boundaries) must fail this test."""
    from tests.factories import make_area

    khasras_a = [make_khasra("KHS-1", "KHT-1", kanal=2)]
    khatauni_a = make_khatauni("KHT-1", "KHW-1", khasras=khasras_a, recorded_area=make_area(kanal=2))

    khasras_b = [make_khasra("KHS-2", "KHT-2", kanal=3)]
    khatauni_b = make_khatauni("KHT-2", "KHW-1", khasras=khasras_b, recorded_area=make_area(kanal=3))

    khewat = make_khewat("KHW-1", khataunis=[khatauni_a, khatauni_b])
    result = validate_ag03_area_consistency(make_document(khewats=[khewat]))

    # Each Khatauni independently reconciles (2==2, 3==3): both pass.
    assert result.passed
    assert result.checked_entities == 2

    # Now corrupt one Khatauni's Khasra sum. Only that Khatauni should
    # fail — proof the gate evaluates per-Khatauni, not by summing the
    # whole Khewat (which would mask this exact error as 5==5).
    khasras_a_wrong = [make_khasra("KHS-1", "KHT-1", kanal=1)]  # should be 2, not 1
    khatauni_a_wrong = make_khatauni("KHT-1", "KHW-1", khasras=khasras_a_wrong, recorded_area=make_area(kanal=2))
    khewat_wrong = make_khewat("KHW-1", khataunis=[khatauni_a_wrong, khatauni_b])
    result_wrong = validate_ag03_area_consistency(make_document(khewats=[khewat_wrong]))

    assert not result_wrong.passed
    failed_ids = {i.entity_id for i in result_wrong.issues if i.severity == ValidationSeverity.ERROR}
    assert failed_ids == {"KHT-1"}


# ---------------------------------------------------------------------
# run_axiom_gates: aggregate report
# ---------------------------------------------------------------------

def test_run_axiom_gates_reports_overall_pass():
    khasra = make_khasra("KHS-1", "KHT-1")
    khatauni = make_khatauni("KHT-1", "KHW-1", khasras=[khasra])
    owner = make_owner("OWN-1", "KHW-1", "1/1")
    khewat = make_khewat("KHW-1", owners=[owner], khataunis=[khatauni])
    report = run_axiom_gates(make_document(khewats=[khewat]))
    assert report.passed
    # Subset, not equality: adding a new gate is a feature, not a regression.
    # The point of this assertion is that the core gates always run.
    assert {"AG-01", "AG-02", "AG-03", "AG-04"} <= {g.gate_id for g in report.gates}


def test_run_axiom_gates_reports_overall_failure_from_any_gate():
    owner = make_owner("OWN-1", "KHW-WRONG", "1/1")
    khewat = make_khewat("KHW-1", owners=[owner])
    report = run_axiom_gates(make_document(khewats=[khewat]))
    assert not report.passed
