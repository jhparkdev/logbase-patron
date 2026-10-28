import pytest

from app.models import RequestStatus, SimulationStatus
from app.services.simulation_status import compute_overall_status

R = RequestStatus
S = SimulationStatus


@pytest.mark.parametrize(
    ("statuses", "expected"),
    [
        # 아직 시작 전
        ([R.PENDING, R.PENDING], S.PENDING),
        # 종료되지 않은 모델이 하나라도 있으면 RUNNING
        ([R.RUNNING, R.PENDING], S.RUNNING),
        ([R.SUCCESS, R.RUNNING, R.FAILED], S.RUNNING),
        ([R.SUCCESS, R.PENDING], S.RUNNING),
        # 전부 성공
        ([R.SUCCESS, R.SUCCESS], S.SUCCESS),
        # 성공이 1개 이상이면 나머지가 무엇이든 PARTIAL_SUCCESS (T-21, C-02)
        ([R.SUCCESS, R.SUCCESS, R.TIMEOUT], S.PARTIAL_SUCCESS),
        ([R.SUCCESS, R.FAILED, R.FAILED], S.PARTIAL_SUCCESS),
        ([R.SUCCESS, R.CANCELLED], S.PARTIAL_SUCCESS),
        # 성공 없이 전부 사용자 취소 (C-01)
        ([R.CANCELLED, R.CANCELLED, R.CANCELLED], S.CANCELLED),
        # 성공 없음: 전부 실패·Timeout, 또는 실패와 취소 혼합
        ([R.FAILED, R.FAILED, R.FAILED], S.FAILED),
        ([R.FAILED, R.TIMEOUT], S.FAILED),
        ([R.FAILED, R.CANCELLED], S.FAILED),
        # 모델별 취소로 1개만 남은 경우도 허용 (모델 2~4개 규칙은 시작 시점 검증)
        ([R.SUCCESS], S.SUCCESS),
        ([R.CANCELLED], S.CANCELLED),
    ],
)
def test_compute_overall_status(statuses: list[R], expected: S) -> None:
    assert compute_overall_status(statuses) == expected


def test_empty_statuses_is_rejected() -> None:
    with pytest.raises(ValueError):
        compute_overall_status([])
