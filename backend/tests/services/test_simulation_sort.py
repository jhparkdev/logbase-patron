import pytest

from app.services.simulation_sort import (
    InvalidSortColumnError,
    InvalidSortDirectionError,
    SortColumn,
    SortDirection,
    SortSpec,
    parse_sort,
)


def test_allowed_columns_are_exactly_the_seven_in_the_contract() -> None:
    assert {c.value for c in SortColumn} == {
        "started_at",
        "simulation_id",
        "scenario",
        "model_count",
        "overall_status",
        "cost_status",
        "total_cost",
    }


@pytest.mark.parametrize("column", list(SortColumn))
@pytest.mark.parametrize("direction", list(SortDirection))
def test_every_allowed_column_and_direction_is_accepted(
    column: SortColumn, direction: SortDirection
) -> None:
    assert parse_sort(column.value, direction.value) == SortSpec(column, direction)


def test_default_is_latest_first() -> None:
    assert parse_sort(None, None) == SortSpec(SortColumn.STARTED_AT, SortDirection.DESC)


def test_missing_direction_uses_default_direction() -> None:
    assert parse_sort("scenario", None) == SortSpec(
        SortColumn.SCENARIO, SortDirection.DESC
    )


def test_missing_column_uses_default_column() -> None:
    assert parse_sort(None, "asc") == SortSpec(SortColumn.STARTED_AT, SortDirection.ASC)


@pytest.mark.parametrize(
    "column",
    [
        "",  # 빈 문자열은 "없음"이 아니라 잘못된 값이다
        "unknown",
        "cost_usd",  # 내부 컬럼 이름은 열어 주지 않는다
        "STARTED_AT",  # 대소문자까지 정확히 일치해야 한다
        " started_at",
        "started_at ",
        "started_at; DROP TABLE simulation_runs",
    ],
)
def test_column_outside_allow_list_is_rejected(column: str) -> None:
    with pytest.raises(InvalidSortColumnError) as error:
        parse_sort(column, "asc")
    assert error.value.column == column


@pytest.mark.parametrize("direction", ["", "ASC", "Desc", "up", "ascending"])
def test_direction_outside_allow_list_is_rejected(direction: str) -> None:
    with pytest.raises(InvalidSortDirectionError) as error:
        parse_sort("started_at", direction)
    assert error.value.direction == direction
