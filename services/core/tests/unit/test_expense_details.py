"""报销 details 按类型校验（v4）。"""

from datetime import date

import pytest

from app.common.errors import BizError
from app.crm.schemas.finance import ExpenseDetails
from app.crm.services.expense_details import MAX_NIGHTS, clean_details


def _loc(exc: pytest.ExceptionInfo[BizError]) -> list[str]:
    return exc.value.data["errors"][0]["loc"]  # type: ignore[index]


def test_entertainment_drops_details() -> None:
    assert clean_details("entertainment", ExpenseDetails(city="深圳")) is None


def test_transport_optional_and_trimmed() -> None:
    assert clean_details("transport", None) is None
    d = ExpenseDetails(from_city="深圳", to_city="北京", transport_mode="train", city="x")
    assert clean_details("transport", d) == {
        "from_city": "深圳",
        "to_city": "北京",
        "transport_mode": "train",
    }


def test_hotel_ok() -> None:
    d = ExpenseDetails(city="北京", check_in=date(2026, 10, 1), check_out=date(2026, 10, 3))
    assert clean_details("hotel", d) == {
        "city": "北京",
        "check_in": "2026-10-01",
        "check_out": "2026-10-03",
    }


@pytest.mark.parametrize(
    ("details", "field"),
    [
        (None, "city"),
        (ExpenseDetails(city="北京"), "check_in"),
        (
            ExpenseDetails(city="北京", check_in=date(2026, 10, 3), check_out=date(2026, 10, 3)),
            "check_out",
        ),
        (
            ExpenseDetails(city="北京", check_in=date(2026, 1, 1), check_out=date(2026, 6, 1)),
            "check_out",
        ),
    ],
)
def test_hotel_invalid(details: ExpenseDetails | None, field: str) -> None:
    with pytest.raises(BizError) as exc:
        clean_details("hotel", details)
    assert exc.value.code == 40001 and _loc(exc) == ["body", "details", field]


def test_max_nights_is_reasonable() -> None:
    assert 30 <= MAX_NIGHTS <= 90
