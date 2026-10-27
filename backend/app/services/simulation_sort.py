from dataclasses import dataclass
from enum import StrEnum


class SortColumn(StrEnum):
    STARTED_AT = "started_at"
    SIMULATION_ID = "simulation_id"
    SCENARIO = "scenario"
    MODEL_COUNT = "model_count"
    OVERALL_STATUS = "overall_status"
    COST_STATUS = "cost_status"
    TOTAL_COST = "total_cost"


class SortDirection(StrEnum):
    ASC = "asc"
    DESC = "desc"


DEFAULT_SORT_COLUMN = SortColumn.STARTED_AT
DEFAULT_SORT_DIRECTION = SortDirection.DESC


@dataclass(frozen=True)
class SortSpec:
    column: SortColumn
    direction: SortDirection


class InvalidSortColumnError(ValueError):
    """허용 목록에 없는 정렬 열이 들어왔다."""

    def __init__(self, column: str) -> None:
        super().__init__("허용하지 않은 정렬 열이다")
        self.column = column


class InvalidSortDirectionError(ValueError):
    """asc, desc 가 아닌 정렬 방향이 들어왔다."""

    def __init__(self, direction: str) -> None:
        super().__init__("허용하지 않은 정렬 방향이다")
        self.direction = direction


def parse_sort(column: str | None, direction: str | None) -> SortSpec:
    """이력 목록의 정렬 열·방향을 허용 목록으로 검증한다. None 은 기본값을 쓴다."""
    return SortSpec(
        column=_parse_column(column),
        direction=_parse_direction(direction),
    )


def _parse_column(column: str | None) -> SortColumn:
    if column is None:
        return DEFAULT_SORT_COLUMN
    try:
        return SortColumn(column)
    except ValueError:
        raise InvalidSortColumnError(column) from None


def _parse_direction(direction: str | None) -> SortDirection:
    if direction is None:
        return DEFAULT_SORT_DIRECTION
    try:
        return SortDirection(direction)
    except ValueError:
        raise InvalidSortDirectionError(direction) from None
