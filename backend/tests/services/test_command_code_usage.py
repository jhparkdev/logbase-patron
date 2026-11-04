"""services/command_code_usage.py 테스트. 구성원마다 한 줄을 만들고, 한 명의 실패가 다른 줄에 번지지 않는지 본다."""

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.command_code import CommandCodeStatus
from app.services.command_code_result import FetchResult, UsageSnapshot
from app.services.command_code_usage import list_member_usage
from tests.db_helpers import Factory

NOW = datetime(2026, 11, 3, 1, 0, tzinfo=UTC)
# 테스트용 가짜 값. 실제 Key가 아니다
KEYS = {
    "COMMAND_CODE_KEY_HONG": "key-hong",
    "COMMAND_CODE_KEY_KIM": "key-kim",
}


def _snapshot(used: str) -> UsageSnapshot:
    return UsageSnapshot(
        used_credits=Decimal(used),
        request_count=10,
        input_tokens=100,
        output_tokens=20,
        remaining_credits=Decimal("62.5"),
        period_start=datetime(2026, 10, 20, 2, 4, 33, tzinfo=UTC),
        period_end=datetime(2026, 11, 20, 2, 4, 33, tzinfo=UTC),
    )


class FakeFetch:
    """Key별로 정해 둔 결과를 돌려주고, 어떤 Key로 물었는지 기록한다."""

    def __init__(self, results: dict[str, FetchResult]) -> None:
        self.results = results
        self.asked: list[str] = []

    async def __call__(self, api_key: str) -> FetchResult:
        self.asked.append(api_key)
        return self.results[api_key]


def _ok(used: str) -> FetchResult:
    return FetchResult(status=CommandCodeStatus.OK, snapshot=_snapshot(used))


def _failed(status: CommandCodeStatus) -> FetchResult:
    return FetchResult(status=status)


async def _member(factory: Factory, name: str, key_name: str, **values: Any) -> None:
    await factory.command_code_key(
        member_name=name, secret_ref=f"COMMAND_CODE_KEY_{key_name}", **values
    )


async def test_구성원마다_한_줄씩_이름순으로_돌려준다(
    db_session: AsyncSession, factory: Factory
) -> None:
    await _member(factory, "홍길동", "HONG")
    await _member(factory, "김철수", "KIM")
    fetch = FakeFetch({"key-hong": _ok("1.5"), "key-kim": _ok("2.5")})

    rows = await list_member_usage(db_session, keys=KEYS, fetch=fetch, now=NOW)

    assert [row.member_name for row in rows] == ["김철수", "홍길동"]
    assert [row.used_credits for row in rows] == [Decimal("2.5"), Decimal("1.5")]


async def test_정상인_줄은_사용량_전체와_조회_시각을_담는다(
    db_session: AsyncSession, factory: Factory
) -> None:
    await _member(factory, "홍길동", "HONG")
    fetch = FakeFetch({"key-hong": _ok("1.5")})

    [row] = await list_member_usage(db_session, keys=KEYS, fetch=fetch, now=NOW)

    assert row.status == CommandCodeStatus.OK
    assert row.request_count == 10
    assert (row.input_tokens, row.output_tokens) == (100, 20)
    assert row.remaining_credits == Decimal("62.5")
    assert row.period_start == datetime(2026, 10, 20, 2, 4, 33, tzinfo=UTC)
    assert row.period_end == datetime(2026, 11, 20, 2, 4, 33, tzinfo=UTC)
    assert row.fetched_at == NOW


async def test_한_명이_실패해도_다른_구성원은_정상이다(
    db_session: AsyncSession, factory: Factory
) -> None:
    await _member(factory, "홍길동", "HONG")
    await _member(factory, "김철수", "KIM")
    fetch = FakeFetch(
        {
            "key-hong": _ok("1.5"),
            "key-kim": _failed(CommandCodeStatus.KEY_EXPIRED),
        }
    )

    rows = await list_member_usage(db_session, keys=KEYS, fetch=fetch, now=NOW)

    by_name = {row.member_name: row for row in rows}
    assert by_name["홍길동"].status == CommandCodeStatus.OK
    assert by_name["김철수"].status == CommandCodeStatus.KEY_EXPIRED


async def test_실패한_줄의_값은_0이_아니라_모두_null이다(
    db_session: AsyncSession, factory: Factory
) -> None:
    await _member(factory, "홍길동", "HONG")
    fetch = FakeFetch({"key-hong": _failed(CommandCodeStatus.FETCH_FAILED)})

    [row] = await list_member_usage(db_session, keys=KEYS, fetch=fetch, now=NOW)

    assert row.status == CommandCodeStatus.FETCH_FAILED
    assert row.used_credits is None
    assert row.request_count is None
    assert row.input_tokens is None
    assert row.output_tokens is None
    assert row.remaining_credits is None
    assert row.period_start is None
    assert row.period_end is None
    assert row.fetched_at == NOW


async def test_환경변수에_Key가_없으면_KEY_MISSING이고_조회하지_않는다(
    db_session: AsyncSession, factory: Factory
) -> None:
    await _member(factory, "홍길동", "HONG")
    await _member(factory, "박영희", "PARK")
    fetch = FakeFetch({"key-hong": _ok("1.5")})

    rows = await list_member_usage(db_session, keys=KEYS, fetch=fetch, now=NOW)

    by_name = {row.member_name: row for row in rows}
    assert by_name["박영희"].status == CommandCodeStatus.KEY_MISSING
    assert by_name["홍길동"].status == CommandCodeStatus.OK
    assert fetch.asked == ["key-hong"]


async def test_Key가_빈_문자열이면_없는_것으로_본다(
    db_session: AsyncSession, factory: Factory
) -> None:
    await _member(factory, "홍길동", "HONG")
    fetch = FakeFetch({})

    [row] = await list_member_usage(
        db_session,
        keys={"COMMAND_CODE_KEY_HONG": "  "},
        fetch=fetch,
        now=NOW,
    )

    assert row.status == CommandCodeStatus.KEY_MISSING
    assert fetch.asked == []


async def test_사용하지_않는_구성원은_조회하지_않고_목록에서_뺀다(
    db_session: AsyncSession, factory: Factory
) -> None:
    await _member(factory, "홍길동", "HONG")
    await _member(factory, "김철수", "KIM", is_active=False)
    fetch = FakeFetch({"key-hong": _ok("1.5")})

    rows = await list_member_usage(db_session, keys=KEYS, fetch=fetch, now=NOW)

    assert [row.member_name for row in rows] == ["홍길동"]
    assert fetch.asked == ["key-hong"]


async def test_등록된_구성원이_없으면_빈_목록이다(db_session: AsyncSession) -> None:
    fetch = FakeFetch({})

    rows = await list_member_usage(db_session, keys=KEYS, fetch=fetch, now=NOW)

    assert rows == []
    assert fetch.asked == []
