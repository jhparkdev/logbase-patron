MIN_MODEL_COUNT = 2
MAX_MODEL_COUNT = 4


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
