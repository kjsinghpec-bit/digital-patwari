from __future__ import annotations

from fractions import Fraction

from digital_patwari.models import (
    DigitalPatwariDocument,
    GateResult,
    RemarkTarget,
    ValidationIssue,
    ValidationReport,
    ValidationSeverity,
)
from digital_patwari.ownership import owners_by_khatauni, pooled_owners as pooled_owners_of


def validate_ag01_khewat_share_summation(document: DigitalPatwariDocument) -> GateResult:
    """Real Fards routinely split one Khewat into Khataunis with disjoint
    owner groups (verified against samples/real_fard/Chaman Lal Sanghol.pdf,
    Khewat 219: two Khataunis, each independently summing to 1, sharing no
    owners). Pooling every owner in the Khewat together and expecting them
    to sum to the Khewat's total_share is wrong whenever any owner carries
    a khatauni_id -- each such group must be checked against its OWN
    Khatauni's total_share instead. Owners with no khatauni_id (pooled,
    whole-Khewat ownership) keep the original pooled check."""
    issues: list[ValidationIssue] = []
    checked, skipped = 0, 0

    for khewat in document.khewats:
        pooled = pooled_owners_of(khewat)
        scoped_by_khatauni = owners_by_khatauni(khewat)

        if not pooled and not scoped_by_khatauni:
            skipped += 1
            issues.append(ValidationIssue(
                gate_id="AG-01", severity=ValidationSeverity.WARNING, entity_type="Khewat",
                entity_id=khewat.khewat_id, expected=str(khewat.expected_total_share),
                message="Share summation skipped: no owners extracted."
            ))
            continue

        if pooled:
            checked += 1
            actual_total = sum((owner.fraction for owner in pooled), Fraction(0))
            expected_total = khewat.expected_total_share

            if actual_total != expected_total:
                difference = actual_total - expected_total
                issues.append(ValidationIssue(
                    gate_id="AG-01", severity=ValidationSeverity.ERROR, entity_type="Khewat",
                    entity_id=khewat.khewat_id, expected=str(expected_total), actual=str(actual_total),
                    difference=str(difference), message="Owner shares do not sum to Khewat total."
                ))

        khataunis_by_id = {kht.khatauni_id: kht for kht in khewat.khataunis}
        for khatauni_id, owners in scoped_by_khatauni.items():
            checked += 1
            khatauni = khataunis_by_id.get(khatauni_id)
            expected_total = khatauni.expected_total_share if khatauni is not None else Fraction(1)
            actual_total = sum((owner.fraction for owner in owners), Fraction(0))

            if actual_total != expected_total:
                difference = actual_total - expected_total
                issues.append(ValidationIssue(
                    gate_id="AG-01", severity=ValidationSeverity.ERROR, entity_type="Khatauni",
                    entity_id=khatauni_id, expected=str(expected_total), actual=str(actual_total),
                    difference=str(difference),
                    message="Khatauni-scoped owner shares do not sum to that Khatauni's total_share."
                ))

    return GateResult(
        gate_id="AG-01", passed=not any(i.severity == ValidationSeverity.ERROR for i in issues),
        checked_entities=checked, skipped_entities=skipped, issues=issues
    )


def _record_duplicate_ids(issues: list[ValidationIssue], entity_type: str, ids: list[str]) -> None:
    seen: set[str] = set()
    for entity_id in ids:
        if entity_id in seen:
            issues.append(ValidationIssue(
                gate_id="AG-02", severity=ValidationSeverity.ERROR, entity_type=entity_type,
                entity_id=entity_id, message=f"Duplicate {entity_type} ID: not globally unique."
            ))
        seen.add(entity_id)


def validate_ag02_linkage_and_integrity(document: DigitalPatwariDocument) -> GateResult:
    issues: list[ValidationIssue] = []
    checked = 0

    khewat_ids = [khw.khewat_id for khw in document.khewats]
    khatauni_ids = [kht.khatauni_id for khw in document.khewats for kht in khw.khataunis]
    owner_ids = [own.owner_id for khw in document.khewats for own in khw.owners]
    khasra_ids = [
        khs.khasra_id for khw in document.khewats for kht in khw.khataunis for khs in kht.khasras
    ]
    mutation_ids = [m.mutation_id for m in document.mutations]
    _record_duplicate_ids(issues, "Khewat", khewat_ids)
    _record_duplicate_ids(issues, "Khatauni", khatauni_ids)
    _record_duplicate_ids(issues, "Owner", owner_ids)
    _record_duplicate_ids(issues, "Khasra", khasra_ids)
    _record_duplicate_ids(issues, "Mutation", mutation_ids)

    active_khataunis = {kht.khatauni_id: kht for khw in document.khewats for kht in khw.khataunis}
    entities_by_type: dict[RemarkTarget, set[str]] = {
        RemarkTarget.KHEWAT: set(khewat_ids),
        RemarkTarget.KHATAUNI: set(khatauni_ids),
        RemarkTarget.OWNER: set(owner_ids),
        RemarkTarget.KHASRA: set(khasra_ids),
    }

    for khewat in document.khewats:
        khataunis_in_this_khewat = {kht.khatauni_id for kht in khewat.khataunis}
        for owner in khewat.owners:
            checked += 1
            if owner.khewat_id != khewat.khewat_id:
                issues.append(ValidationIssue(
                    gate_id="AG-02", severity=ValidationSeverity.ERROR, entity_type="Owner",
                    entity_id=owner.owner_id, expected=khewat.khewat_id, actual=owner.khewat_id,
                    message="Owner.khewat_id does not match its containing Khewat."
                ))
            if owner.khatauni_id is not None and owner.khatauni_id not in khataunis_in_this_khewat:
                issues.append(ValidationIssue(
                    gate_id="AG-02", severity=ValidationSeverity.ERROR, entity_type="Owner",
                    entity_id=owner.owner_id, expected="an existing Khatauni within this Owner's Khewat",
                    actual=owner.khatauni_id,
                    message="Owner.khatauni_id does not resolve to a Khatauni within this Owner's Khewat."
                ))

        for container in khewat.khataunis:
            checked += 1
            if container.khewat_id != khewat.khewat_id:
                issues.append(ValidationIssue(
                    gate_id="AG-02", severity=ValidationSeverity.ERROR, entity_type="Khatauni",
                    entity_id=container.khatauni_id, expected=khewat.khewat_id, actual=container.khewat_id,
                    message="Khatauni.khewat_id does not match its containing Khewat."
                ))

            for khasra in container.khasras:
                checked += 1
                if active_khataunis.get(khasra.khatauni_id) is None or khasra.khatauni_id != container.khatauni_id:
                    issues.append(ValidationIssue(
                        gate_id="AG-02", severity=ValidationSeverity.ERROR, entity_type="Khasra",
                        entity_id=khasra.khasra_id, expected=container.khatauni_id, actual=khasra.khatauni_id,
                        message="Khasra foreign key missing or mismatched."
                    ))

    for remark in document.remarks:
        checked += 1
        valid_ids = entities_by_type.get(remark.target_type, set())
        if remark.target_id not in valid_ids:
            issues.append(ValidationIssue(
                gate_id="AG-02", severity=ValidationSeverity.ERROR, entity_type="Remark",
                entity_id=remark.target_id, expected=f"existing {remark.target_type.value}",
                actual=remark.target_id, message="Remark.target_id does not resolve to an entity of its declared target_type."
            ))

    for mutation in document.mutations:
        checked += 1
        valid_ids = entities_by_type.get(mutation.target_type, set())
        if mutation.target_id not in valid_ids:
            issues.append(ValidationIssue(
                gate_id="AG-02", severity=ValidationSeverity.ERROR, entity_type="Mutation",
                entity_id=mutation.target_id, expected=f"existing {mutation.target_type.value}",
                actual=mutation.target_id, message="Mutation.target_id does not resolve to an entity of its declared target_type."
            ))

    return GateResult(
        gate_id="AG-02",
        passed=not any(i.severity == ValidationSeverity.ERROR for i in issues),
        checked_entities=checked, skipped_entities=0, issues=issues
    )


def validate_ag03_area_consistency(
    document: DigitalPatwariDocument,
    marla_per_kanal: int = 20,
    sarsahi_per_marla: int = 9,
    tolerance_marla: int = 0,
) -> GateResult:
    issues: list[ValidationIssue] = []
    checked, skipped = 0, 0
    tolerance_sarsahi = tolerance_marla * sarsahi_per_marla

    for khewat in document.khewats:
        for khatauni in khewat.khataunis:
            if khatauni.recorded_total_area is None or not khatauni.khasras:
                skipped += 1
                issues.append(ValidationIssue(
                    gate_id="AG-03", severity=ValidationSeverity.WARNING, entity_type="Khatauni",
                    entity_id=khatauni.khatauni_id, message="Area consistency skipped (missing records or Khasras)."
                ))
                continue

            checked += 1
            expected_sarsahi = khatauni.recorded_total_area.total_sarsahi(marla_per_kanal, sarsahi_per_marla)
            actual_sarsahi = sum(
                k.area_kanal_marla.total_sarsahi(marla_per_kanal, sarsahi_per_marla) for k in khatauni.khasras
            )
            difference = actual_sarsahi - expected_sarsahi

            if abs(difference) > tolerance_sarsahi:
                issues.append(ValidationIssue(
                    gate_id="AG-03", severity=ValidationSeverity.ERROR, entity_type="Khatauni",
                    entity_id=khatauni.khatauni_id, expected=f"{expected_sarsahi} sarsahi",
                    actual=f"{actual_sarsahi} sarsahi", difference=f"{difference:+d} sarsahi",
                    message="Sum of Khasra areas != recorded Khatauni total (checked to the sarsahi)."
                ))

    return GateResult(
        gate_id="AG-03", passed=not any(i.severity == ValidationSeverity.ERROR for i in issues),
        checked_entities=checked, skipped_entities=skipped, issues=issues
    )


def _all_source_references(document: DigitalPatwariDocument) -> list:
    sources = []
    if document.document_header.source:
        sources.append(document.document_header.source)
    for khewat in document.khewats:
        if khewat.source:
            sources.append(khewat.source)
        for owner in khewat.owners:
            if owner.source:
                sources.append(owner.source)
        for khatauni in khewat.khataunis:
            if khatauni.source:
                sources.append(khatauni.source)
            for khasra in khatauni.khasras:
                if khasra.source:
                    sources.append(khasra.source)
    for remark in document.remarks:
        if remark.source:
            sources.append(remark.source)
    for mutation in document.mutations:
        if mutation.source:
            sources.append(mutation.source)
    return sources


def validate_ag04_document_completeness(document: DigitalPatwariDocument) -> GateResult:
    """A page printed as "Page 5 of 8" states the Fard has 8 pages. If the
    extracted document only carries evidence from fewer than 8 distinct
    pages, the upload is incomplete -- CLAUDE.md's Zero-Guesswork Guardrail
    requires flagging that rather than silently analyzing a partial Fard."""
    sources = _all_source_references(document)
    stated_totals = {s.total_pages for s in sources if s.total_pages is not None}

    if not stated_totals:
        return GateResult(
            gate_id="AG-04", passed=True, checked_entities=0, skipped_entities=1,
            issues=[ValidationIssue(
                gate_id="AG-04", severity=ValidationSeverity.WARNING, entity_type="Document",
                entity_id=document.document_header.village,
                message="Document completeness check skipped: no page states a total page count.",
            )],
        )

    issues: list[ValidationIssue] = []
    page_numbers = {s.page_number for s in sources}
    max_stated = max(stated_totals)

    if len(stated_totals) > 1:
        issues.append(ValidationIssue(
            gate_id="AG-04", severity=ValidationSeverity.WARNING, entity_type="Document",
            entity_id=document.document_header.village,
            message=f"Inconsistent total-page counts found across the document: {sorted(stated_totals)}.",
        ))

    if len(page_numbers) < max_stated:
        missing = sorted(set(range(1, max_stated + 1)) - page_numbers)
        issues.append(ValidationIssue(
            gate_id="AG-04", severity=ValidationSeverity.ERROR, entity_type="Document",
            entity_id=document.document_header.village,
            expected=str(max_stated), actual=str(len(page_numbers)),
            message=(
                f"Incomplete document: the record indicates {max_stated} page(s), but evidence from "
                f"only {len(page_numbers)} distinct page(s) is present. Missing page(s): "
                f"{', '.join(str(p) for p in missing)}."
            ),
        ))

    return GateResult(
        gate_id="AG-04",
        passed=not any(i.severity == ValidationSeverity.ERROR for i in issues),
        checked_entities=1, skipped_entities=0, issues=issues,
    )


def validate_ag05_mutation_share_area_consistency(
    document: DigitalPatwariDocument,
    marla_per_kanal: int = 20,
    sarsahi_per_marla: int = 9,
) -> GateResult:
    """When a mutation records BOTH a transferred share and a transferred
    area, the two must agree against the correct ownership scope. If they
    disagree, one of them was misread -- flag MUTATION_SHARE_AREA_MISMATCH
    rather than silently trusting whichever is convenient."""
    issues: list[ValidationIssue] = []
    checked, skipped = 0, 0

    khewats_by_id = {k.khewat_id: k for k in document.khewats}

    for mutation in document.mutations:
        if mutation.share_transferred is None or mutation.area_transferred is None:
            skipped += 1
            continue

        khewat = None
        if mutation.target_type == RemarkTarget.KHEWAT:
            khewat = khewats_by_id.get(mutation.target_id)
        elif mutation.target_type == RemarkTarget.OWNER:
            for candidate in document.khewats:
                if any(o.owner_id == mutation.target_id for o in candidate.owners):
                    khewat = candidate
                    break
        if khewat is None:
            skipped += 1
            continue

        scope_sarsahi = 0
        incomplete = False
        for khatauni in khewat.khataunis:
            if khatauni.recorded_total_area is None:
                incomplete = True
                continue
            scope_sarsahi += khatauni.recorded_total_area.total_sarsahi(marla_per_kanal, sarsahi_per_marla)
        if incomplete or scope_sarsahi == 0:
            skipped += 1
            continue

        checked += 1
        expected = Fraction(scope_sarsahi) * mutation.transferred_fraction
        stated = Fraction(mutation.area_transferred.total_sarsahi(marla_per_kanal, sarsahi_per_marla))
        if expected != stated:
            issues.append(ValidationIssue(
                gate_id="AG-05", severity=ValidationSeverity.ERROR, entity_type="Mutation",
                entity_id=mutation.mutation_id,
                expected=f"{expected} sarsahi (share {mutation.share_transferred} of scope)",
                actual=f"{stated} sarsahi (area as recorded)",
                difference=f"{stated - expected} sarsahi",
                message="MUTATION_SHARE_AREA_MISMATCH: recorded transferred share and recorded transferred area disagree.",
            ))

    return GateResult(
        gate_id="AG-05",
        passed=not any(i.severity == ValidationSeverity.ERROR for i in issues),
        checked_entities=checked, skipped_entities=skipped, issues=issues,
    )


def validate_ag06_area_observation_scopes(
    document: DigitalPatwariDocument,
    marla_per_kanal: int = 20,
    sarsahi_per_marla: int = 9,
) -> GateResult:
    """Guard the physical-area-uniqueness invariant across AreaObservations.

    The same physical land is printed several times in a Fard (parcel line,
    Khatauni subtotal, Khewat total). Those are representations, not
    addends. This gate flags a repeated identical total inside the same
    scope+entity -- a repeated printed total is NOT additional land."""
    issues: list[ValidationIssue] = []
    checked = 0

    seen: dict[tuple, list[str]] = {}
    for observation in document.area_observations:
        checked += 1
        key = (
            observation.scope,
            observation.khewat_id,
            observation.khatauni_id,
            observation.khasra_id,
            observation.area.total_sarsahi(marla_per_kanal, sarsahi_per_marla),
        )
        seen.setdefault(key, []).append(observation.observation_id)

    for key, observation_ids in seen.items():
        if len(observation_ids) > 1:
            scope, khewat_id, khatauni_id, khasra_id, sarsahi = key
            issues.append(ValidationIssue(
                gate_id="AG-06", severity=ValidationSeverity.WARNING, entity_type="AreaObservation",
                entity_id=", ".join(observation_ids),
                expected="one observation per (scope, entity, value)",
                actual=f"{len(observation_ids)} identical {scope.value} observations of {sarsahi} sarsahi",
                message=(
                    "Repeated identical area total within the same scope. A total printed more than "
                    "once is the same land restated, not additional land -- count it once."
                ),
            ))

    return GateResult(
        gate_id="AG-06", passed=True,  # advisory: repetition is normal in Fards, silent addition is the bug
        checked_entities=checked, skipped_entities=0, issues=issues,
    )


def validate_ag07_parcel_interest_resolution(document: DigitalPatwariDocument) -> GateResult:
    """Every ParcelInterest must name Khasras that actually exist within its
    declared Khewat, and must not name the same parcel twice."""
    issues: list[ValidationIssue] = []
    checked = 0

    khewats_by_id = {k.khewat_id: k for k in document.khewats}

    for interest in document.parcel_interests:
        checked += 1
        khewat = khewats_by_id.get(interest.khewat_id)
        if khewat is None:
            issues.append(ValidationIssue(
                gate_id="AG-07", severity=ValidationSeverity.ERROR, entity_type="ParcelInterest",
                entity_id=interest.parcel_interest_id,
                expected="an existing Khewat", actual=interest.khewat_id,
                message="ParcelInterest.khewat_id does not resolve to a Khewat in this document.",
            ))
            continue

        available = {
            khasra.khasra_id
            for khatauni in khewat.khataunis
            for khasra in khatauni.khasras
        }
        missing = [kid for kid in interest.khasra_ids if kid not in available]
        if missing:
            issues.append(ValidationIssue(
                gate_id="AG-07", severity=ValidationSeverity.ERROR, entity_type="ParcelInterest",
                entity_id=interest.parcel_interest_id,
                expected=f"Khasras within Khewat {interest.khewat_id}",
                actual=", ".join(missing),
                message="ParcelInterest names Khasra(s) not present in its declared Khewat.",
            ))

        duplicates = {kid for kid in interest.khasra_ids if interest.khasra_ids.count(kid) > 1}
        if duplicates:
            issues.append(ValidationIssue(
                gate_id="AG-07", severity=ValidationSeverity.ERROR, entity_type="ParcelInterest",
                entity_id=interest.parcel_interest_id,
                actual=", ".join(sorted(duplicates)),
                message=(
                    "ParcelInterest names the same Khasra more than once; one physical parcel must "
                    "not contribute twice to the same calculation."
                ),
            ))

        if not interest.khasra_ids:
            issues.append(ValidationIssue(
                gate_id="AG-07", severity=ValidationSeverity.WARNING, entity_type="ParcelInterest",
                entity_id=interest.parcel_interest_id,
                message=(
                    "ParcelInterest names no Khasras; its scope cannot be established from the record. "
                    "Do not fall back to the whole Khewat -- verification required."
                ),
            ))

    return GateResult(
        gate_id="AG-07",
        passed=not any(i.severity == ValidationSeverity.ERROR for i in issues),
        checked_entities=checked, skipped_entities=0, issues=issues,
    )


def run_axiom_gates(
    document: DigitalPatwariDocument,
    marla_per_kanal: int = 20,
    sarsahi_per_marla: int = 9,
    area_tolerance_marla: int = 0,
) -> ValidationReport:
    gates = [
        validate_ag01_khewat_share_summation(document),
        validate_ag02_linkage_and_integrity(document),
        validate_ag03_area_consistency(
            document, marla_per_kanal=marla_per_kanal,
            sarsahi_per_marla=sarsahi_per_marla, tolerance_marla=area_tolerance_marla,
        ),
        validate_ag04_document_completeness(document),
        validate_ag05_mutation_share_area_consistency(
            document, marla_per_kanal=marla_per_kanal, sarsahi_per_marla=sarsahi_per_marla,
        ),
        validate_ag06_area_observation_scopes(
            document, marla_per_kanal=marla_per_kanal, sarsahi_per_marla=sarsahi_per_marla,
        ),
        validate_ag07_parcel_interest_resolution(document),
    ]
    return ValidationReport(passed=all(g.passed for g in gates), gates=gates)
