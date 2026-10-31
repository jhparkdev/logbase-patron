from collections.abc import Sequence
from dataclasses import dataclass

from app.models import ModelStatus

MIN_MODEL_COUNT = 2
MAX_MODEL_COUNT = 4


@dataclass(frozen=True)
class ModelSelection:
    """비교 실행에서 고른 모델 하나. 필드 이름은 simulation_results 컬럼과 같은 의미다."""

    model_id: int  # models 표의 model_id
    execution_provider: str  # 실행 Provider. 자동 라우팅 없이 반드시 지정한다


class DuplicateModelSelectionError(ValueError):
    """같은 모델을 같은 Provider 로 두 번 골랐다."""

    def __init__(self, selection: ModelSelection) -> None:
        super().__init__("같은 모델을 같은 Provider 로 중복 선택할 수 없다")
        self.selection = selection


class ModelCountError(ValueError):
    """비교 실행에 선택한 모델 수가 허용 범위를 벗어났다."""

    def __init__(self, count: int) -> None:
        super().__init__(
            f"모델은 {MIN_MODEL_COUNT}~{MAX_MODEL_COUNT}개여야 한다 (요청: {count}개)"
        )
        self.count = count


def validate_model_count(count: int) -> None:
    """실행을 시작할 때 선택한 모델 수가 허용 범위 안인지 확인한다.

    실행 중 모델별 취소로 1개만 남는 것은 허용하므로, 시작 시점에만 호출한다.
    """
    if not MIN_MODEL_COUNT <= count <= MAX_MODEL_COUNT:
        raise ModelCountError(count)


def validate_model_selection(selections: Sequence[ModelSelection]) -> None:
    """선택한 모델 목록의 개수(2~4개)와 중복(같은 모델 + 같은 Provider)을 검사한다."""
    validate_model_count(len(selections))

    seen: set[ModelSelection] = set()
    for selection in selections:
        if selection in seen:
            raise DuplicateModelSelectionError(selection)
        seen.add(selection)


def is_model_selectable(status: ModelStatus) -> bool:
    """일반 비교 실행에서 고를 수 있는 모델인지 판단한다. ACTIVE 만 가능하다.

    TESTING 은 관리자 모델 관리의 연결 테스트에서만 쓰고, INACTIVE 는 신규 실행에서 제외한다.
    """
    return status == ModelStatus.ACTIVE
