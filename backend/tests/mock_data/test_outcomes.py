"""app/mock_data/outcomes.py 테스트: 호출 결과와 실패 유형."""

from random import Random

from app.mock_data import outcomes
from app.models import ErrorType, RequestStatus


def test_failure_outcomes_match_the_status_and_error_rule() -> None:
    for error_type, outcome in outcomes.FAILURES.items():
        assert outcome.error_type == error_type
        assert outcome.status in (RequestStatus.FAILED, RequestStatus.TIMEOUT)


def test_failure_rate_is_close_to_the_requested_rate() -> None:
    rng = Random(5)
    sampled = [outcomes.sample_outcome(0.05, rng) for _ in range(4000)]
    failed = sum(1 for o in sampled if o.status != RequestStatus.SUCCESS)

    assert 0.04 < failed / len(sampled) < 0.06


def test_only_transient_failures_are_retried() -> None:
    retryable = {e for e, outcome in outcomes.FAILURES.items() if outcome.retryable}

    assert retryable == {
        ErrorType.RATE_LIMIT,
        ErrorType.PROVIDER_ERROR,
        ErrorType.TIMEOUT_ERROR,
        ErrorType.NETWORK_ERROR,
    }
