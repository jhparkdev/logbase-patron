"""구성원별 Command Code 사용량(P-02). 구성원마다 한 줄을 만들고, 한 명의 실패가 다른 줄에 번지지 않게 한다.

크레딧 사용량은 구독에 포함된 값이라 실제 지출이 아니다. 비용 합계에 더하지 않고, 조회 기간도 적용하지
않는다(결제 기간 기준).
"""

import asyncio
from collections.abc import Awaitable, Callable, Mapping
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import CommandCodeKey
from app.schemas.command_code import CommandCodeMemberUsage, CommandCodeStatus
from app.services.command_code_result import FetchResult

# Key 원문을 받아 사용량을 조회한다. 실패해도 예외 없이 FetchResult로 돌려준다
UsageFetcher = Callable[[str], Awaitable[FetchResult]]


def _row(
    member_name: str, result: FetchResult, fetched_at: datetime
) -> CommandCodeMemberUsage:
    # 읽지 못한 줄은 값을 채우지 않아 모두 null이 된다(0으로 바꾸지 않는다)
    values = {} if result.snapshot is None else result.snapshot.model_dump()
    return CommandCodeMemberUsage(
        member_name=member_name,
        status=result.status,
        fetched_at=fetched_at,
        **values,
    )


async def list_member_usage(
    session: AsyncSession,
    *,
    keys: Mapping[str, str],
    fetch: UsageFetcher,
    now: datetime,
) -> list[CommandCodeMemberUsage]:
    """사용 중인 구성원을 이름순으로 한 줄씩 돌려준다. keys는 secret_ref → Key 원문이다."""
    members = (
        await session.execute(
            select(CommandCodeKey.member_name, CommandCodeKey.secret_ref)
            .where(CommandCodeKey.is_active)
            .order_by(CommandCodeKey.member_name)
        )
    ).all()

    async def read(member_name: str, secret_ref: str) -> CommandCodeMemberUsage:
        api_key = keys.get(secret_ref, "").strip()
        if not api_key:
            missing = FetchResult(status=CommandCodeStatus.KEY_MISSING)
            return _row(member_name, missing, now)
        return _row(member_name, await fetch(api_key), now)

    return list(await asyncio.gather(*(read(name, ref) for name, ref in members)))
