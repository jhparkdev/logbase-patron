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
    # 이름은 v_simulation_summary 의 열 이름을 따른다. total_cost 는 DB 에 대응 열이 없어 임시다
    assert {c.value for c in SortColumn} == {
        "requested_at",
        "simulation_id",
        "scenario_code",
        "model_count",
        "status",
        "cost_check_status",
        "total_cost",
    }


@pytest.mark.parametrize("column", list(SortColumn))
@pytest.mark.parametrize("direction", list(SortDirection))
def test_every_allowed_column_and_direction_is_accepted(
    column: SortColumn, direction: SortDirection
) -> None:
    assert parse_sort(column.value, direction.value) == SortSpec(column, direction)


def test_default_is_latest_first() -> None:
    assert parse_sort(None, None) == SortSpec(
        SortColumn.REQUESTED_AT, SortDirection.DESC
    )


def test_missing_direction_uses_default_direction() -> None:
    assert parse_sort("scenario_code", None) == SortSpec(
        SortColumn.SCENARIO_CODE, SortDirection.DESC
    )


def test_missing_column_uses_default_column() -> None:
    assert parse_sort(None, "asc") == SortSpec(
        SortColumn.REQUESTED_AT, SortDirection.ASC
    )


@pytest.mark.parametrize(
    "column",
    [
        "",  # 빈 문자열은 "없음"이 아니라 잘못된 값이다
        "unknown",
        "cost_usd",  # 내부 컬럼 이름은 열어 주지 않는다
        "started_at",  # 이전 이름. DB 열 이름(requested_at)을 쓴다
        "overall_status",  # 이전 이름. DB 열 이름(status)을 쓴다
        "REQUESTED_AT",  # 대소문자까지 정확히 일치해야 한다
        " requested_at",
        "requested_at ",
        "requested_at; DROP TABLE simulation_runs",
    ],
)
def test_column_outside_allow_list_is_rejected(column: str) -> None:
    with pytest.raises(InvalidSortColumnError) as error:
        parse_sort(column, "asc")
    assert error.value.column == column


@pytest.mark.parametrize("direction", ["", "ASC", "Desc", "up", "ascending"])
def test_direction_outside_allow_list_is_rejected(direction: str) -> None:
    with pytest.raises(InvalidSortDirectionError) as error:
        parse_sort("requested_at", direction)
    assert error.value.direction == direction
