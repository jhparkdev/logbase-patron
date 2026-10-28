import pytest

from app.models import RequestStatus
from app.services.simulation_cancel import CancelDecision, decide_request_cancel

R = RequestStatus
D = CancelDecision

EXPECTED = {
    # 아직 끝나지 않은 건만 취소한다
    R.PENDING: D.CANCEL,
    R.RUNNING: D.CANCEL,
    # 같은 취소를 두 번 눌러도 결과가 같다 (C-08)
    R.CANCELLED: D.ALREADY_CANCELLED,
    # 이미 끝난 결과와 비용은 건드리지 않는다 (C-09)
    R.SUCCESS: D.ALREADY_TERMINAL,
    R.FAILED: D.ALREADY_TERMINAL,
    R.TIMEOUT: D.ALREADY_TERMINAL,
}


@pytest.mark.parametrize(("status", "expected"), EXPECTED.items())
def test_decide_request_cancel(status: R, expected: D) -> None:
    assert decide_request_cancel(status) == expected


def test_every_status_has_an_expected_decision() -> None:
    # 상태가 새로 생기면 이 표에도 판정을 추가하도록 강제한다
    assert set(EXPECTED) == set(R)
