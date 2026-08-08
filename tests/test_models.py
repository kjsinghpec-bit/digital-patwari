import pydantic
import pytest

from patwari_agent import AreaKanalMarlaSarsahi, ExtractionStatus, Owner
from tests.factories import make_owner


def test_area_total_marla():
    area = AreaKanalMarlaSarsahi(kanal=2, marla=5)
    assert area.total_marla() == 45  # 2*20 + 5


def test_area_total_sarsahi():
    area = AreaKanalMarlaSarsahi(kanal=1, marla=2, sarsahi=3)
    # 1 kanal = 20 marla -> 22 marla total -> 22*9 + 3 = 201 sarsahi
    assert area.total_sarsahi() == 201


def test_owner_with_unresolved_share_cannot_remain_present():
    from patwari_agent import ExtractionStatus
    from tests.factories import make_owner

    owner = make_owner(
        "OWN-X", "KHW-X", "1/2",
        share_fraction=None,
        status=ExtractionStatus.PRESENT,
    )
    assert owner.share_fraction is None
    assert owner.status == ExtractionStatus.UNCERTAIN


def test_corrected_owner_share_can_be_present_again():
    from patwari_agent import ExtractionStatus
    from tests.factories import make_owner

    owner = make_owner(
        "OWN-X", "KHW-X", "1/2",
        share_fraction=None,
        status=ExtractionStatus.UNCERTAIN,
    )
    corrected = type(owner).model_validate({
        **owner.model_dump(), "share_fraction": "1/4", "status": "present",
    })
    assert corrected.share_fraction == "1/4"
    assert corrected.status.value == "present"


def test_area_rejects_negative_kanal():
    with pytest.raises(pydantic.ValidationError):
        AreaKanalMarlaSarsahi(kanal=-1)


def test_area_defaults_are_illegible_safe():
    area = AreaKanalMarlaSarsahi()
    assert area.status == ExtractionStatus.PRESENT
    assert area.total_marla() == 0


def test_owner_share_fraction_is_normalized():
    owner = make_owner("OWN-1", "KHW-1", "2/4")
    assert owner.share_fraction == "1/2"
    assert owner.fraction == owner.fraction  # sanity: Fraction property works


def test_owner_rejects_extra_fields():
    with pytest.raises(pydantic.ValidationError):
        Owner(
            owner_id="OWN-1",
            khewat_id="KHW-1",
            raw_owner_name_parentage="X",
            raw_share_fraction="1/2",
            share_fraction="1/2",
            unexpected_field="should be rejected",
        )


def test_owner_zero_guesswork_status_uncertain_allowed():
    owner = make_owner("OWN-1", "KHW-1", "1/2", status=ExtractionStatus.UNCERTAIN)
    assert owner.status == ExtractionStatus.UNCERTAIN
