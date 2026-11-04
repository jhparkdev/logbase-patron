"""services/command_code_parsing.py 테스트. 2026-11-03 실제 키로 확인한 응답 모양을 쓴다."""

from copy import deepcopy
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import pytest

from app.schemas.command_code import CommandCodeStatus
from app.services.command_code_parsing import classify_error, parse_snapshot

SUMMARY: dict[str, Any] = {
    "totalCount": 2379,
    "totalCredits": Decimal("27.6518301021"),
    "completedCount": 2376,
    "failedCount": 3,
    "totalTokensIn": 816632167,
    "totalTokensOut": 1987270,
    "periodStart": "2026-10-20T02:04:33.000Z",
    "daily": [],
}
CREDITS: dict[str, Any] = {
    "credits": {"monthlyCredits": Decimal("62.3745912155"), "purchasedCredits": 0}
}
SUBSCRIPTION: dict[str, Any] = {
    "success": True,
    "data": {
        "status": "active",
        "currentPeriodStart": "2026-10-20T02:04:33.000Z",
        "currentPeriodEnd": "2026-11-20T02:04:33.000Z",
    },
}


def test_실제_응답_모양에서_표에_쓸_값을_뽑는다() -> None:
    snapshot = parse_snapshot(SUMMARY, CREDITS, SUBSCRIPTION)

    assert snapshot is not None
    assert snapshot.used_credits == Decimal("27.6518301021")
    assert snapshot.request_count == 2379
    assert snapshot.input_tokens == 816632167
    assert snapshot.output_tokens == 1987270
    assert snapshot.remaining_credits == Decimal("62.3745912155")
    assert snapshot.period_start == datetime(2026, 10, 20, 2, 4, 33, tzinfo=UTC)
    assert snapshot.period_end == datetime(2026, 11, 20, 2, 4, 33, tzinfo=UTC)


def test_사용량이_0이어도_값으로_읽는다() -> None:
    summary = {**SUMMARY, "totalCount": 0, "totalCredits": 0, "totalTokensIn": 0}

    snapshot = parse_snapshot(summary, CREDITS, SUBSCRIPTION)

    assert snapshot is not None
    assert snapshot.used_credits == Decimal(0)
    assert snapshot.request_count == 0


def _without(body: dict[str, Any], *path: str) -> dict[str, Any]:
    copied = deepcopy(body)
    target = copied
    for name in path[:-1]:
        target = target[name]
    del target[path[-1]]
    return copied


@pytest.mark.parametrize(
    ("summary", "credits", "subscription"),
    [
        (_without(SUMMARY, "totalCredits"), CREDITS, SUBSCRIPTION),
        (_without(SUMMARY, "totalCount"), CREDITS, SUBSCRIPTION),
        (_without(SUMMARY, "totalTokensIn"), CREDITS, SUBSCRIPTION),
        (_without(SUMMARY, "totalTokensOut"), CREDITS, SUBSCRIPTION),
        (SUMMARY, _without(CREDITS, "credits", "monthlyCredits"), SUBSCRIPTION),
        (SUMMARY, CREDITS, _without(SUBSCRIPTION, "data", "currentPeriodStart")),
        (SUMMARY, CREDITS, _without(SUBSCRIPTION, "data", "currentPeriodEnd")),
    ],
)
def test_필요한_값이_하나라도_없으면_읽지_못한_것이다(
    summary: dict[str, Any], credits: dict[str, Any], subscription: dict[str, Any]
) -> None:
    assert parse_snapshot(summary, credits, subscription) is None


@pytest.mark.parametrize(
    "broken",
    [
        {"totalCredits": "27.6"},
        {"totalCredits": -1},
        {"totalCredits": True},
        {"totalCredits": None},
        {"totalCount": 1.5},
        {"totalCount": -1},
        {"totalCount": True},
        {"totalTokensOut": "1987270"},
    ],
)
def test_숫자가_아니거나_음수이면_읽지_못한_것이다(broken: dict[str, Any]) -> None:
    assert parse_snapshot({**SUMMARY, **broken}, CREDITS, SUBSCRIPTION) is None


@pytest.mark.parametrize(
    "bad_time",
    [
        "어제",
        "",
        None,
        20261120,
        "2026-11-20T02:04:33",
    ],
)
def test_결제_기간이_시각이_아니거나_시간대가_없으면_읽지_못한_것이다(
    bad_time: Any,
) -> None:
    subscription = deepcopy(SUBSCRIPTION)
    subscription["data"]["currentPeriodEnd"] = bad_time

    assert parse_snapshot(SUMMARY, CREDITS, subscription) is None


@pytest.mark.parametrize("body", [None, [], "text", 1, {}])
def test_본문이_예상한_모양이_아니면_읽지_못한_것이다(body: Any) -> None:
    assert parse_snapshot(body, CREDITS, SUBSCRIPTION) is None
    assert parse_snapshot(SUMMARY, body, SUBSCRIPTION) is None
    assert parse_snapshot(SUMMARY, CREDITS, body) is None


def _error_body(message: str) -> dict[str, Any]:
    return {
        "success": False,
        "error": {"code": "UNAUTHORIZED", "status": 401, "message": message},
    }


def test_만료_문구가_있는_401은_키_만료이다() -> None:
    body = _error_body("Your API key has expired.")

    assert classify_error(401, body) == CommandCodeStatus.KEY_EXPIRED


def test_틀린_키의_401은_키_오류이다() -> None:
    body = _error_body("Invalid 'Authorization' header or token.")

    assert classify_error(401, body) == CommandCodeStatus.KEY_INVALID


@pytest.mark.parametrize("body", [None, {}, "text", {"error": "x"}, {"error": {}}])
def test_문구를_알_수_없는_401은_키_오류이다(body: Any) -> None:
    assert classify_error(401, body) == CommandCodeStatus.KEY_INVALID


@pytest.mark.parametrize("status_code", [400, 403, 404, 429, 500, 502, 503])
def test_401이_아닌_오류는_수집_실패이다(status_code: int) -> None:
    body = _error_body("Your API key has expired.")

    assert classify_error(status_code, body) == CommandCodeStatus.FETCH_FAILED
