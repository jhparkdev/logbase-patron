from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from app.models import ModelStatus
from app.openrouter.lookup_result import ReasoningInfo
from app.schemas.simulation import ReasoningEffort
from app.services.model_registry import (
    AvailabilityStatus,
    PriceSnapshot,
    StatusChangeError,
    build_metadata,
    check_status_change,
    judge_availability,
    price_changed,
    provider_from_model_id,
    snapshot_from_pricing,
    stored_reasoning_efforts,
    supports_json_schema,
    supports_tools,
)

TESTING = ModelStatus.TESTING
ACTIVE = ModelStatus.ACTIVE
INACTIVE = ModelStatus.INACTIVE
NOW = datetime(2026, 10, 31, 12, 0, tzinfo=UTC)
DAY = timedelta(hours=24)
RECENT = NOW - timedelta(hours=1)


# ---------------------------------------------------------------
# 상태 변경 규칙
# ---------------------------------------------------------------
@pytest.mark.parametrize(
    ("current", "target"),
    [(TESTING, INACTIVE), (ACTIVE, INACTIVE)],
)
@pytest.mark.parametrize("last_success_test_at", [None, RECENT, NOW - 30 * DAY])
def test_비활성으로_바꾸는_것은_테스트_기록과_상관없이_허용한다(
    current: ModelStatus, target: ModelStatus, last_success_test_at: datetime | None
) -> None:
    assert check_status_change(current, target, last_success_test_at, NOW) is None


@pytest.mark.parametrize("current", [TESTING, INACTIVE])
@pytest.mark.parametrize(
    "elapsed",
    [timedelta(0), timedelta(hours=23, minutes=59), DAY],
    ids=["방금", "23시간 59분", "정확히 24시간"],
)
def test_24시간_안에_성공한_테스트가_있으면_ACTIVE로_바꿀_수_있다(
    current: ModelStatus, elapsed: timedelta
) -> None:
    assert check_status_change(current, ACTIVE, NOW - elapsed, NOW) is None


@pytest.mark.parametrize("current", [TESTING, INACTIVE])
@pytest.mark.parametrize(
    "last_success_test_at",
    [
        None,
        NOW - DAY - timedelta(seconds=1),
        NOW - DAY - timedelta(minutes=1),
        NOW - 3 * DAY,
    ],
    ids=["성공 기록 없음", "24시간 1초", "24시간 1분", "3일"],
)
def test_24시간_안에_성공한_테스트가_없으면_ACTIVE로_바꿀_수_없다(
    current: ModelStatus, last_success_test_at: datetime | None
) -> None:
    error = check_status_change(current, ACTIVE, last_success_test_at, NOW)

    assert error == StatusChangeError.TEST_NOT_PASSED


@pytest.mark.parametrize(
    ("current", "target"),
    [
        (ACTIVE, TESTING),
        (INACTIVE, TESTING),
        (TESTING, TESTING),
        (ACTIVE, ACTIVE),
        (INACTIVE, INACTIVE),
    ],
)
def test_허용하지_않는_전이는_INVALID_STATUS_TRANSITION이다(
    current: ModelStatus, target: ModelStatus
) -> None:
    error = check_status_change(current, target, RECENT, NOW)

    assert error == StatusChangeError.INVALID_STATUS_TRANSITION


def test_허용하지_않는_전이가_테스트_미통과보다_먼저_판단된다() -> None:
    error = check_status_change(ACTIVE, ACTIVE, None, NOW)

    assert error == StatusChangeError.INVALID_STATUS_TRANSITION


def test_알_수_없는_상태_값은_거절한다() -> None:
    error = check_status_change("DELETED", ACTIVE, RECENT, NOW)

    assert error == StatusChangeError.INVALID_STATUS_TRANSITION


# ---------------------------------------------------------------
# 제공 중단 감지 (목록 비교)
# ---------------------------------------------------------------
def test_OpenRouter_목록에_있으면_제공_중이다() -> None:
    status = judge_availability("a/b", {"a/b", "c/d"})

    assert status == AvailabilityStatus.AVAILABLE


def test_목록에_없으면_제공_중단_의심이다() -> None:
    status = judge_availability("a/b", {"c/d"})

    assert status == AvailabilityStatus.SUSPECTED_DISCONTINUED


def test_목록을_받지_못했으면_판단하지_않는다() -> None:
    assert judge_availability("a/b", None) == AvailabilityStatus.UNKNOWN


def test_목록이_비어_있으면_조회가_잘못된_것으로_보고_판단하지_않는다() -> None:
    assert judge_availability("a/b", set()) == AvailabilityStatus.UNKNOWN


def test_모델_ID는_대소문자를_구분해_비교한다() -> None:
    status = judge_availability("A/B", {"a/b"})

    assert status == AvailabilityStatus.SUSPECTED_DISCONTINUED


# ---------------------------------------------------------------
# 지원 기능과 제공사
# ---------------------------------------------------------------
@pytest.mark.parametrize(
    ("parameters", "expected"),
    [
        (["temperature", "response_format"], True),
        ([], False),
        (["temperature", "structured_outputs"], False),
    ],
)
def test_response_format이_있으면_JSON_Schema를_지원한다(
    parameters: list[str], expected: bool
) -> None:
    assert supports_json_schema(parameters) is expected


@pytest.mark.parametrize(
    ("parameters", "expected"),
    [
        (["temperature", "tools"], True),
        ([], False),
        (["temperature", "tool_choice"], False),
    ],
)
def test_tools가_있으면_함수_호출을_지원한다(
    parameters: list[str], expected: bool
) -> None:
    assert supports_tools(parameters) is expected


@pytest.mark.parametrize(
    ("model_id", "expected"),
    [
        ("mistralai/mistral-nemo", "mistralai"),
        ("a/b/c", "a"),
        ("no-slash", None),
        ("", None),
        ("/name", None),
    ],
)
def test_모델_ID의_앞부분이_제공사다(model_id: str, expected: str | None) -> None:
    assert provider_from_model_id(model_id) == expected


# ---------------------------------------------------------------
# 가격 비교
# ---------------------------------------------------------------
def test_OpenRouter_가격에서_입력_출력_캐시_단가를_꺼낸다() -> None:
    pricing = {
        "prompt": Decimal("0.000002"),
        "completion": Decimal("0.00001"),
        "input_cache_read": Decimal("0.0000002"),
        "input_cache_write": Decimal("0.0000025"),
        "web_search": Decimal(1),
    }

    snapshot = snapshot_from_pricing(pricing)

    assert snapshot == PriceSnapshot(
        input_price_per_token=Decimal("0.000002"),
        output_price_per_token=Decimal("0.00001"),
        cache_read_price_per_token=Decimal("0.0000002"),
        cache_write_price_per_token=Decimal("0.0000025"),
    )


def test_캐시_단가가_없으면_None으로_둔다() -> None:
    snapshot = snapshot_from_pricing(
        {"prompt": Decimal("0.1"), "completion": Decimal("0.2")}
    )

    assert snapshot is not None
    assert snapshot.cache_read_price_per_token is None
    assert snapshot.cache_write_price_per_token is None


@pytest.mark.parametrize(
    "pricing",
    [
        {},
        {"prompt": Decimal("0.1")},
        {"completion": Decimal("0.2")},
        {"input_cache_read": Decimal("0.1")},
    ],
)
def test_입력_또는_출력_단가가_없으면_가격_미확인이다(
    pricing: dict[str, Decimal],
) -> None:
    assert snapshot_from_pricing(pricing) is None


@pytest.mark.parametrize(
    "pricing",
    [
        {"prompt": Decimal(-1), "completion": Decimal("0.2")},
        {"prompt": Decimal("0.1"), "completion": Decimal(-1)},
    ],
)
def test_단가가_음수이면_가격_미확인이다(pricing: dict[str, Decimal]) -> None:
    assert snapshot_from_pricing(pricing) is None


def test_단가가_0이면_무료로_보고_가격은_확인된_것이다() -> None:
    snapshot = snapshot_from_pricing({"prompt": Decimal(0), "completion": Decimal(0)})

    assert snapshot is not None
    assert snapshot.input_price_per_token == 0


def snapshot(input_price: str, output_price: str) -> PriceSnapshot:
    return PriceSnapshot(
        input_price_per_token=Decimal(input_price),
        output_price_per_token=Decimal(output_price),
        cache_read_price_per_token=None,
        cache_write_price_per_token=None,
    )


def test_처음_받은_가격은_새_가격이다() -> None:
    assert price_changed(None, snapshot("0.1", "0.2")) is True


def test_단가가_같으면_바뀌지_않은_것이다() -> None:
    assert price_changed(snapshot("0.1", "0.2"), snapshot("0.1", "0.2")) is False


def test_표기만_다른_같은_금액은_바뀌지_않은_것이다() -> None:
    assert price_changed(snapshot("0.1", "0.2"), snapshot("0.10", "0.200")) is False


def test_단가가_하나라도_다르면_바뀐_것이다() -> None:
    assert price_changed(snapshot("0.1", "0.2"), snapshot("0.1", "0.3")) is True


def test_캐시_단가가_생기면_바뀐_것이다() -> None:
    old = snapshot("0.1", "0.2")
    new = PriceSnapshot(
        input_price_per_token=Decimal("0.1"),
        output_price_per_token=Decimal("0.2"),
        cache_read_price_per_token=Decimal("0.01"),
        cache_write_price_per_token=None,
    )

    assert price_changed(old, new) is True


# ---------------------------------------------------------------
# 모델별 추론 강도 (등록할 때 저장한 정보)
# ---------------------------------------------------------------
EFFORT = ReasoningEffort


def stored(efforts: list[str] | None, mandatory: bool = False) -> dict[str, object]:
    return {"reasoning": {"mandatory": mandatory, "supported_efforts": efforts}}


def test_추론_정보가_없으면_저장할_메타데이터도_없다() -> None:
    assert build_metadata(None) is None


def test_추론_정보를_메타데이터로_만든다() -> None:
    reasoning = ReasoningInfo(mandatory=True, supported_efforts=["high", "low"])

    assert build_metadata(reasoning) == stored(["high", "low"], mandatory=True)


def test_모든_강도를_받는_모델은_강도_목록이_null로_저장된다() -> None:
    reasoning = ReasoningInfo(mandatory=False, supported_efforts=None)

    assert build_metadata(reasoning) == stored(None)


@pytest.mark.parametrize(
    "metadata",
    [
        None,
        {},
        {"reasoning": "문자열"},
        {"reasoning": {"mandatory": False}},
        {"reasoning": {"supported_efforts": "high"}},
    ],
    ids=["저장 안 함", "빈 값", "모양이 다름", "강도 목록 없음", "강도가 문자열"],
)
def test_저장된_정보가_없거나_모양이_틀리면_None이다(
    metadata: dict[str, object] | None,
) -> None:
    assert stored_reasoning_efforts(metadata) is None


def test_저장된_강도를_고정된_순서로_돌려준다() -> None:
    efforts = stored_reasoning_efforts(stored(["high", "minimal", "medium", "low"]))

    assert efforts == (EFFORT.MINIMAL, EFFORT.LOW, EFFORT.MEDIUM, EFFORT.HIGH)


def test_모르는_강도는_버린다() -> None:
    assert stored_reasoning_efforts(stored(["high", "turbo"])) == (EFFORT.HIGH,)


def test_강도_목록이_null이면_모든_강도를_받는다() -> None:
    assert stored_reasoning_efforts(stored(None)) == tuple(EFFORT)


def test_강도를_고를_수_없는_모델은_빈_튜플이다() -> None:
    assert stored_reasoning_efforts(stored([])) == ()


def test_추론이_필수인_모델에는_none을_허용하지_않는다() -> None:
    listed = stored_reasoning_efforts(stored(["none", "low"], mandatory=True))
    all_efforts = stored_reasoning_efforts(stored(None, mandatory=True))

    assert listed == (EFFORT.LOW,)
    assert all_efforts == tuple(effort for effort in EFFORT if effort != EFFORT.NONE)
