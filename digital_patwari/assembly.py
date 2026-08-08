"""Deterministic conversion and human verification of page observations."""
from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel, ValidationError

from digital_patwari.merge import merge_page_documents
from digital_patwari.models import (
    AreaObservation,
    CultivationInterest,
    DigitalPatwariDocument,
    DocumentHeader,
    ExtractionStatus,
    Khasra,
    Khatauni,
    Khewat,
    Mutation,
    Owner,
    ParcelInterest,
    Remark,
)
from digital_patwari.observations import (
    FieldObservation,
    PageObservation,
    StructuralConfirmation,
    StructuralCorrectionRecord,
    StructuralCorrectionRequest,
    StructuralOperationType,
    VerificationAction,
    VerificationIssue,
    VerificationReason,
    VerificationRecord,
    VerificationResponse,
    VerificationStatus,
)


@dataclass(frozen=True)
class PageAssemblyResult:
    page_number: int
    document: DigitalPatwariDocument | None
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    verification_issues: tuple[VerificationIssue, ...] = ()


@dataclass(frozen=True)
class DocumentAssemblyResult:
    document: DigitalPatwariDocument | None
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    successful_pages: tuple[int, ...] = ()
    failed_pages: tuple[int, ...] = ()
    verification_issues: tuple[VerificationIssue, ...] = ()
    has_trustworthy_header: bool = True

    @property
    def unresolved_critical_issues(self) -> tuple[VerificationIssue, ...]:
        return tuple(issue for issue in self.verification_issues if issue.critical and not issue.resolved)


@dataclass(frozen=True)
class VerificationApplicationResult:
    observations: tuple[PageObservation, ...]
    assembly: DocumentAssemblyResult
    record: VerificationRecord


@dataclass(frozen=True)
class StructuralApplicationResult:
    observations: tuple[PageObservation, ...]
    assembly: DocumentAssemblyResult
    record: StructuralCorrectionRecord
    affected_pages: tuple[int, ...]


_ROW_MODEL_BY_COLLECTION = {
    "khewats": Khewat,
    "owners": Owner,
    "khataunis": Khatauni,
    "khasras": Khasra,
    "remarks": Remark,
    "mutations": Mutation,
    "parcel_interests": ParcelInterest,
    "cultivation_interests": CultivationInterest,
    "area_observations": AreaObservation,
}


def _payload_dict(observation: PageObservation) -> dict[str, Any]:
    payload = observation.canonical_payload
    return payload.model_dump(mode="python") if isinstance(payload, BaseModel) else copy.deepcopy(payload)


def _format_error(error: dict[str, Any]) -> str:
    location = ".".join(str(part) for part in error["loc"])
    return f"{location}: {error['msg']}"


def _path_parent(payload: Any, path: tuple[Any, ...]) -> tuple[Any, Any] | None:
    if not path:
        return None
    target = payload
    try:
        for part in path[:-1]:
            target = target[part]
        return target, path[-1]
    except (KeyError, IndexError, TypeError):
        return None


def _matching_field(observation: PageObservation, path: tuple[Any, ...]) -> FieldObservation | None:
    for item in observation.fields:
        if tuple(item.field_path) == path:
            return item
    return None


def _issue_for_invalid_field(
    observation: PageObservation,
    path: tuple[Any, ...],
    actual: Any,
) -> VerificationIssue:
    field = _matching_field(observation, path)
    field_id = field.observation_id if field else f"auto-p{observation.page_number}-{'-'.join(map(str, path))}"
    label = path[-1] if path else "value"
    return VerificationIssue(
        issue_id=f"verify-{field_id}",
        field_observation_id=field_id,
        page_number=observation.page_number,
        field_path=list(path),
        reason=VerificationReason.INVALID_FORMAT,
        question=f"What should the recorded {str(label).replace('_', ' ')} be?",
        proposed_value=actual,
        depends_on="Calculations using this field are paused until it is verified.",
        critical=True,
    )


def _repair_field_without_dropping_row(
    candidate: dict[str, Any],
    observation: PageObservation,
    error: dict[str, Any],
) -> tuple[str, VerificationIssue] | None:
    """Make only known unsafe fields non-calculable; retain their entity row."""
    path = tuple(error["loc"])
    located = _path_parent(candidate, path)
    if located is None:
        return None
    parent, key = located
    actual = parent.get(key) if isinstance(parent, dict) else None

    # Owner share: raw_share_fraction remains byte-for-byte evidence while the
    # normalized calculation input becomes None.
    if key == "share_fraction" and "owners" in path:
        parent[key] = None
        parent["status"] = ExtractionStatus.UNCERTAIN.value
    # Optional arithmetic inputs on other rows are similarly quarantined.
    elif key == "share_transferred" and "mutations" in path:
        parent[key] = None
        parent["extraction_status"] = ExtractionStatus.UNCERTAIN.value
    elif key == "share_fraction" and "cultivation_interests" in path:
        parent[key] = None
        parent["status"] = ExtractionStatus.UNCERTAIN.value
    elif key == "total_share" and ("khewats" in path or "khataunis" in path):
        # Preserve raw_total_share and every structural identifier/child row.
        parent[key] = None
    elif key in {"kanal", "marla", "sarsahi"} and any(
        marker in path for marker in {"area_kanal_marla", "recorded_total_area", "area_transferred", "area"}
    ):
        # The area object itself supports unresolved components. Never coerce
        # malformed text to zero; calculations check Area.calculable.
        parent[key] = None
        parent["status"] = ExtractionStatus.UNCERTAIN.value
    else:
        return None

    return (
        f"page {observation.page_number}: retained row and excluded invalid {'.'.join(map(str, path))} from calculations",
        _issue_for_invalid_field(observation, path, actual),
    )


def assemble_page_observation(
    observation: PageObservation,
    *,
    header_override: DocumentHeader | None = None,
) -> PageAssemblyResult:
    candidate = _payload_dict(observation)
    warnings: list[str] = []
    issues = list(observation.verification_issues)
    if header_override is not None:
        candidate["document_header"] = header_override.model_dump(mode="python")

    repaired_paths: set[tuple[Any, ...]] = set()
    while True:
        try:
            document = DigitalPatwariDocument.model_validate(candidate)
            deduped = {issue.issue_id: issue for issue in issues}
            return PageAssemblyResult(
                observation.page_number, document, warnings, [], tuple(deduped.values())
            )
        except ValidationError as exc:
            repaired = False
            for error in exc.errors():
                path = tuple(error["loc"])
                if path in repaired_paths:
                    continue
                outcome = _repair_field_without_dropping_row(candidate, observation, error)
                if outcome is not None:
                    warning, issue = outcome
                    warnings.append(warning)
                    issues.append(issue)
                    repaired_paths.add(path)
                    repaired = True
            if not repaired:
                return PageAssemblyResult(
                    observation.page_number,
                    None,
                    warnings,
                    [_format_error(error) for error in exc.errors()],
                    tuple({issue.issue_id: issue for issue in issues}.values()),
                )


def _trusted_header(observations: list[PageObservation]) -> tuple[DocumentHeader | None, int | None]:
    for observation in sorted(observations, key=lambda item: item.page_number):
        payload = _payload_dict(observation)
        try:
            return DocumentHeader.model_validate(payload.get("document_header")), observation.page_number
        except ValidationError:
            continue
    return None, None


def _placeholder_header() -> DocumentHeader:
    return DocumentHeader(
        village="[verification required]",
        hadbast_number="[verification required]",
        jamabandi_year="[verification required]",
        lr_number="[verification required]",
    )


def assemble_page_observations(observations: list[PageObservation]) -> DocumentAssemblyResult:
    if not observations:
        return DocumentAssemblyResult(None, errors=["no page observations supplied"])

    trusted_header, trusted_page = _trusted_header(observations)
    has_trustworthy_header = trusted_header is not None
    header_for_invalid_pages = trusted_header or _placeholder_header()
    page_documents: list[tuple[int, DigitalPatwariDocument]] = []
    warnings: list[str] = []
    errors: list[str] = []
    issues: list[VerificationIssue] = []
    failed_pages: list[int] = []

    if not has_trustworthy_header:
        warnings.append("no trustworthy document header was extracted; body retained with a verification placeholder")
        first_page_number = min(observation.page_number for observation in observations)
        issues.append(VerificationIssue(
            issue_id="verify-document-header",
            field_observation_id="document-header",
            page_number=first_page_number,
            field_path=["document_header"],
            reason=VerificationReason.INVALID_FORMAT,
            question="What are the village, Hadbast number, Jamabandi year and LR number shown in the header?",
            depends_on="The record cannot be treated as a complete identified document until its header is verified.",
            critical=True,
        ))

    for observation in sorted(observations, key=lambda item: item.page_number):
        payload = _payload_dict(observation)
        try:
            page_header = DocumentHeader.model_validate(payload.get("document_header"))
            header_override = None
            if trusted_header is not None and page_header != trusted_header:
                # Let merge retain the first verified header and emit its
                # normal disagreement warning for valid-but-conflicting text.
                header_override = None
        except ValidationError:
            header_override = header_for_invalid_pages
            source = f"page {trusted_page}" if trusted_page is not None else "verification placeholder"
            warnings.append(
                f"page {observation.page_number}: repeated header missing/invalid; reused {source}; raw header observation retained"
            )

        result = assemble_page_observation(observation, header_override=header_override)
        warnings.extend(result.warnings)
        issues.extend(result.verification_issues)
        if result.document is None:
            failed_pages.append(result.page_number)
            errors.extend(f"page {result.page_number}: {error}" for error in result.errors)
        else:
            page_documents.append((result.page_number, result.document))

    if not page_documents:
        return DocumentAssemblyResult(
            None, warnings, errors, failed_pages=tuple(failed_pages),
            verification_issues=tuple({i.issue_id: i for i in issues}.values()),
            has_trustworthy_header=has_trustworthy_header,
        )

    merged = merge_page_documents(page_documents)
    warnings.extend(merged.warnings)
    return DocumentAssemblyResult(
        merged.document,
        warnings=warnings,
        errors=errors,
        successful_pages=tuple(page for page, _ in page_documents),
        failed_pages=tuple(failed_pages),
        verification_issues=tuple({i.issue_id: i for i in issues}.values()),
        has_trustworthy_header=has_trustworthy_header,
    )


def _set_path(payload: dict[str, Any], path: list[str | int], value: Any) -> None:
    located = _path_parent(payload, tuple(path))
    if located is None:
        raise ValueError(f"field path no longer exists: {path}")
    parent, key = located
    parent[key] = value


def apply_verification_response(
    observations: list[PageObservation] | tuple[PageObservation, ...],
    response: VerificationResponse,
) -> VerificationApplicationResult:
    """Apply a human answer to a copy and reassemble without provider access."""
    updated_pages = [page.model_copy(deep=True) for page in observations]
    target_page: PageObservation | None = None
    issue: VerificationIssue | None = None
    field_observation: FieldObservation | None = None
    for page in updated_pages:
        for candidate_issue in page.verification_issues:
            if candidate_issue.issue_id == response.issue_id:
                target_page = page
                issue = candidate_issue
                field_observation = next(
                    (field for field in page.fields if field.observation_id == issue.field_observation_id),
                    None,
                )
                break
        if issue is not None:
            break
    if issue is None:
        generated = assemble_page_observations(updated_pages)
        issue = next(
            (candidate for candidate in generated.verification_issues if candidate.issue_id == response.issue_id),
            None,
        )
        if issue is not None and issue.page_number is not None:
            target_page = next((page for page in updated_pages if page.page_number == issue.page_number), None)
            if target_page is not None and issue.field_path:
                payload = _payload_dict(target_page)
                located = _path_parent(payload, tuple(issue.field_path))
                original = None
                if located is not None:
                    parent, key = located
                    original = parent.get(key) if isinstance(parent, dict) else parent[key]
                field_observation = FieldObservation(
                    observation_id=issue.field_observation_id,
                    field_path=issue.field_path,
                    entity_type="Unclassified canonical row",
                    extracted_value=original,
                    raw_text=str(original) if original is not None else "",
                    page_number=target_page.page_number,
                    column_ref="unknown",
                    verification_status=VerificationStatus.NEEDS_REVIEW,
                    verification_reason=issue.reason,
                    uncertainty_reason="Automatically identified during deterministic schema validation.",
                )
                target_page.fields = [*target_page.fields, field_observation]
                target_page.verification_issues = [*target_page.verification_issues, issue]
    if target_page is None or issue is None or field_observation is None:
        raise ValueError(f"verification issue {response.issue_id!r} is not backed by a field observation")

    if response.action == VerificationAction.CONFIRM:
        chosen = issue.proposed_value if issue.proposed_value is not None else field_observation.extracted_value
        status = VerificationStatus.CONFIRMED
    elif response.action == VerificationAction.SELECT_ALTERNATIVE:
        chosen = response.selected_alternative
        if chosen not in issue.alternatives:
            raise ValueError("selected value is not one of the issue alternatives")
        status = VerificationStatus.CORRECTED
    else:
        chosen = response.correction
        status = VerificationStatus.CORRECTED

    payload = _payload_dict(target_page)
    _set_path(payload, field_observation.field_path, chosen)
    updated_field = field_observation.model_copy(update={
        "corrected_value": chosen if status == VerificationStatus.CORRECTED else None,
        "verification_status": status,
        "verifier_id": response.verifier_id,
        "verification_session_id": response.verification_session_id,
        "verified_at": response.timestamp,
    })
    target_page.canonical_payload = payload
    target_page.fields = [
        updated_field if field.observation_id == updated_field.observation_id else field
        for field in target_page.fields
    ]
    target_page.verification_issues = [
        candidate.model_copy(update={"resolved": True}) if candidate.issue_id == issue.issue_id else candidate
        for candidate in target_page.verification_issues
    ]
    record = VerificationRecord(
        issue_id=issue.issue_id,
        field_observation_id=field_observation.observation_id,
        original_value=field_observation.extracted_value,
        corrected_value=chosen,
        action=response.action,
        verifier_id=response.verifier_id,
        verification_session_id=response.verification_session_id,
        timestamp=response.timestamp,
    )
    target_page.verification_history = [*target_page.verification_history, record]
    assembly = assemble_page_observations(updated_pages)
    return VerificationApplicationResult(tuple(updated_pages), assembly, record)


def _list_at_path(payload: dict[str, Any], path: list[str | int]) -> list[Any]:
    target: Any = payload
    try:
        for part in path:
            target = target[part]
    except (KeyError, IndexError, TypeError) as exc:
        raise ValueError(f"target list path does not exist: {path}") from exc
    if not isinstance(target, list):
        raise ValueError(f"target path is not a row list: {path}")
    return target


def _validated_row(collection: str, row: dict[str, Any]) -> dict[str, Any]:
    model = _ROW_MODEL_BY_COLLECTION.get(collection)
    if model is None:
        raise ValueError(f"unsupported typed row collection: {collection}")
    try:
        return model.model_validate(row).model_dump(mode="python")
    except ValidationError as exc:
        details = "; ".join(_format_error(error) for error in exc.errors())
        raise ValueError(f"corrected {collection} row is invalid: {details}") from exc


def _raw_evidence_for_rows(
    observation: PageObservation,
    target_path: list[str | int],
    row_indices: list[int],
    original_rows: list[dict[str, Any]],
) -> list[str]:
    evidence: list[str] = []
    prefixes = [tuple([*target_path, index]) for index in row_indices]
    for field_observation in observation.fields:
        field_path = tuple(field_observation.field_path)
        if any(field_path[:len(prefix)] == prefix for prefix in prefixes):
            if field_observation.raw_text not in evidence:
                evidence.append(field_observation.raw_text)

    def collect_raw(value: Any, key: str | None = None) -> None:
        if isinstance(value, dict):
            for child_key, child in value.items():
                collect_raw(child, child_key)
        elif isinstance(value, list):
            for child in value:
                collect_raw(child, key)
        elif key is not None and key.startswith("raw_") and value is not None:
            rendered = str(value)
            if rendered not in evidence:
                evidence.append(rendered)

    for row in original_rows:
        collect_raw(row)
    return evidence


def apply_structural_correction(
    observations: list[PageObservation] | tuple[PageObservation, ...],
    request: StructuralCorrectionRequest,
) -> StructuralApplicationResult:
    """Apply one audited structural command to a copy, then reassemble offline."""
    updated_pages = [page.model_copy(deep=True) for page in observations]
    if any(
        record.operation_id == request.operation_id
        for page in updated_pages
        for record in page.structural_history
    ):
        raise ValueError(f"structural correction {request.operation_id!r} already exists")
    target_page = next((page for page in updated_pages if page.page_number == request.page_number), None)
    if target_page is None:
        raise ValueError(f"page {request.page_number} was not found")
    if not request.target_list_path or not isinstance(request.target_list_path[-1], str):
        raise ValueError("target_list_path must end with a typed collection name")
    collection = request.target_list_path[-1]
    if collection not in _ROW_MODEL_BY_COLLECTION:
        raise ValueError(f"unsupported typed row collection: {collection}")

    payload = _payload_dict(target_page)
    rows = _list_at_path(payload, request.target_list_path)
    if len(set(request.row_indices)) != len(request.row_indices):
        raise ValueError("row indices must be unique")
    for index in request.row_indices:
        if index < 0 or index >= len(rows):
            raise ValueError(f"row index {index} is out of range")
    original_rows = [copy.deepcopy(rows[index]) for index in request.row_indices]

    if request.operation == StructuralOperationType.UPDATE_FIELD:
        index = request.row_indices[0]
        corrected = copy.deepcopy(rows[index])
        _set_path(corrected, request.field_path, request.corrected_value)
        corrected_rows = [_validated_row(collection, corrected)]
        rows[index] = corrected_rows[0]
    elif request.operation == StructuralOperationType.ADD_ROW:
        corrected_rows = [_validated_row(collection, request.corrected_rows[0])]
        rows.append(corrected_rows[0])
    elif request.operation == StructuralOperationType.DELETE_ROW:
        corrected_rows = []
        rows.pop(request.row_indices[0])
    elif request.operation == StructuralOperationType.SPLIT_ROW:
        corrected_rows = [_validated_row(collection, row) for row in request.corrected_rows]
        index = request.row_indices[0]
        rows[index:index + 1] = corrected_rows
    elif request.operation == StructuralOperationType.MERGE_ROWS:
        corrected_rows = [_validated_row(collection, request.corrected_rows[0])]
        insert_at = min(request.row_indices)
        for index in sorted(request.row_indices, reverse=True):
            rows.pop(index)
        rows.insert(insert_at, corrected_rows[0])
    else:  # pragma: no cover - exhaustive Enum guard
        raise ValueError(f"unsupported operation: {request.operation}")

    # Validate the corrected page now, before it can enter cross-page merge.
    target_page.canonical_payload = payload
    validation = assemble_page_observation(target_page)
    if validation.document is None:
        raise ValueError("structural correction leaves the page invalid: " + "; ".join(validation.errors))

    raw_evidence = _raw_evidence_for_rows(
        next(page for page in observations if page.page_number == request.page_number),
        request.target_list_path,
        request.row_indices,
        original_rows,
    )
    record = StructuralCorrectionRecord(
        operation_id=request.operation_id,
        operation=request.operation,
        page_number=request.page_number,
        target_list_path=request.target_list_path,
        row_indices=request.row_indices,
        original_rows=original_rows,
        corrected_rows=corrected_rows,
        original_raw_evidence=raw_evidence,
        human_reason=request.human_reason,
        operator_id=request.operator_id,
        verification_session_id=request.verification_session_id,
        timestamp=request.timestamp,
        critical=request.critical,
        verification_status=(
            VerificationStatus.NEEDS_REVIEW if request.critical else VerificationStatus.CORRECTED
        ),
    )
    target_page.structural_history = [*target_page.structural_history, record]
    structural_issue = VerificationIssue(
        issue_id=f"confirm-structural-{request.operation_id}",
        field_observation_id=f"structural-{request.operation_id}",
        page_number=request.page_number,
        field_path=request.target_list_path,
        reason=VerificationReason.STRUCTURAL_CONFLICT,
        question=f"Please confirm the {request.operation.value.replace('_', ' ').lower()} correction on page {request.page_number}.",
        proposed_value=corrected_rows,
        depends_on="Canonical rows and all calculations that use them depend on this structural correction.",
        critical=request.critical,
        resolved=not request.critical,
    )
    target_page.verification_issues = [*target_page.verification_issues, structural_issue]
    assembly = assemble_page_observations(updated_pages)
    return StructuralApplicationResult(tuple(updated_pages), assembly, record, (request.page_number,))


def confirm_structural_correction(
    observations: list[PageObservation] | tuple[PageObservation, ...],
    confirmation: StructuralConfirmation,
) -> StructuralApplicationResult:
    """Explicitly confirm a pending critical structural correction."""
    updated_pages = [page.model_copy(deep=True) for page in observations]
    target_page: PageObservation | None = None
    prior: StructuralCorrectionRecord | None = None
    for page in updated_pages:
        found = next(
            (record for record in page.structural_history if record.operation_id == confirmation.operation_id),
            None,
        )
        if found is not None:
            target_page, prior = page, found
            break
    if target_page is None or prior is None:
        raise ValueError(f"structural correction {confirmation.operation_id!r} was not found")
    if prior.verification_status == VerificationStatus.CONFIRMED:
        raise ValueError(f"structural correction {confirmation.operation_id!r} is already confirmed")

    confirmed = prior.model_copy(update={
        "verification_status": VerificationStatus.CONFIRMED,
        "confirmed_by": confirmation.verifier_id,
        "confirmation_session_id": confirmation.verification_session_id,
        "confirmed_at": confirmation.timestamp,
    })
    target_page.structural_history = [
        confirmed if record.operation_id == confirmation.operation_id else record
        for record in target_page.structural_history
    ]
    issue_id = f"confirm-structural-{confirmation.operation_id}"
    target_page.verification_issues = [
        issue.model_copy(update={"resolved": True}) if issue.issue_id == issue_id else issue
        for issue in target_page.verification_issues
    ]
    assembly = assemble_page_observations(updated_pages)
    return StructuralApplicationResult(
        tuple(updated_pages), assembly, confirmed, (target_page.page_number,)
    )
