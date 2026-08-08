"""Small builder helpers for constructing valid DigitalPatwariDocument
fixtures in tests without repeating boilerplate field values."""
from __future__ import annotations

from patwari_agent import (
    AreaKanalMarlaSarsahi,
    DigitalPatwariDocument,
    DocumentHeader,
    Khasra,
    Khatauni,
    Khewat,
    Mutation,
    MutationStatus,
    Owner,
    Remark,
    RemarkCategory,
    RemarkTarget,
    SourceReference,
)


def make_source(page: int = 1, total_pages=None, **overrides) -> SourceReference:
    fields = dict(page_number=page, total_pages=total_pages)
    fields.update(overrides)
    return SourceReference(**fields)


def make_header(**overrides) -> DocumentHeader:
    fields = dict(
        village="Test Village",
        hadbast_number="123",
        jamabandi_year="2020-21",
        lr_number="LR-1",
    )
    fields.update(overrides)
    return DocumentHeader(**fields)


def make_area(kanal: int = 0, marla: int = 0, sarsahi: int = 0) -> AreaKanalMarlaSarsahi:
    return AreaKanalMarlaSarsahi(kanal=kanal, marla=marla, sarsahi=sarsahi)


def make_owner(owner_id: str, khewat_id: str, share: str, **overrides) -> Owner:
    fields = dict(
        owner_id=owner_id,
        khewat_id=khewat_id,
        raw_owner_name_parentage=f"Owner {owner_id} s/o Father",
        raw_share_fraction=share,
        share_fraction=share,
    )
    fields.update(overrides)
    return Owner(**fields)


def make_khasra(khasra_id: str, khatauni_id: str, kanal: int = 0, marla: int = 0, sarsahi: int = 0, **overrides) -> Khasra:
    fields = dict(
        khasra_id=khasra_id,
        khasra_number=khasra_id.replace("KHS-", ""),
        khatauni_id=khatauni_id,
        area_kanal_marla=make_area(kanal, marla, sarsahi),
    )
    fields.update(overrides)
    return Khasra(**fields)


def make_khatauni(khatauni_id: str, khewat_id: str, khasras=None, recorded_area=None, **overrides) -> Khatauni:
    fields = dict(
        khatauni_id=khatauni_id,
        khewat_id=khewat_id,
        khasras=khasras or [],
        recorded_total_area=recorded_area,
    )
    fields.update(overrides)
    return Khatauni(**fields)


def make_khewat(khewat_id: str, owners=None, khataunis=None, total_share: str = "1/1", **overrides) -> Khewat:
    fields = dict(
        khewat_id=khewat_id,
        raw_total_share=total_share,
        total_share=total_share,
        owners=owners or [],
        khataunis=khataunis or [],
    )
    fields.update(overrides)
    return Khewat(**fields)


def make_remark(target_type: RemarkTarget, target_id: str, category: RemarkCategory, text: str = "remark text") -> Remark:
    return Remark(target_type=target_type, target_id=target_id, remark_category=category, raw_text=text)


def make_mutation(mutation_id: str, target_type: RemarkTarget, target_id: str, status: MutationStatus, **overrides) -> Mutation:
    fields = dict(
        mutation_id=mutation_id,
        target_type=target_type,
        target_id=target_id,
        status=status,
        raw_text="mutation text",
    )
    fields.update(overrides)
    return Mutation(**fields)


def make_parcel_interest(interest_id: str, person: str, khewat_id: str, khasra_ids, **overrides):
    from patwari_agent import ParcelInterest

    fields = dict(
        parcel_interest_id=interest_id,
        person_name=person,
        khewat_id=khewat_id,
        khasra_ids=list(khasra_ids),
    )
    fields.update(overrides)
    return ParcelInterest(**fields)


def make_cultivation_interest(interest_id: str, person: str, khewat_id: str, khatauni_id: str, **overrides):
    from patwari_agent import CultivationInterest

    fields = dict(
        cultivation_interest_id=interest_id,
        person_name=person,
        khewat_id=khewat_id,
        khatauni_id=khatauni_id,
    )
    fields.update(overrides)
    return CultivationInterest(**fields)


def make_area_observation(observation_id: str, scope, kanal: int = 0, marla: int = 0, **overrides):
    from patwari_agent import AreaObservation

    fields = dict(
        observation_id=observation_id,
        scope=scope,
        area=make_area(kanal, marla),
    )
    fields.update(overrides)
    return AreaObservation(**fields)


def make_document(
    khewats=None, remarks=None, mutations=None,
    parcel_interests=None, cultivation_interests=None, area_observations=None,
    **header_overrides,
) -> DigitalPatwariDocument:
    layout = header_overrides.pop("layout", None)
    fields = dict(
        document_header=make_header(**header_overrides),
        khewats=khewats or [],
        remarks=remarks or [],
        mutations=mutations or [],
        parcel_interests=parcel_interests or [],
        cultivation_interests=cultivation_interests or [],
        area_observations=area_observations or [],
    )
    if layout is not None:
        fields["layout"] = layout
    return DigitalPatwariDocument(**fields)
