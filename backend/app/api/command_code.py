"""구성원별 Command Code 사용량(P-02) 경로. 입력 검증과 응답 변환만 하고, 조회는 services가 한다."""

from fastapi import APIRouter

from app.api.command_code_deps import MemberKeysDep, UsageFetcherDep
from app.api.deps import NowDep
from app.db import SessionDep
from app.schemas.command_code import CommandCodeUsageList
from app.services import command_code_usage

router = APIRouter(prefix="/usage/internal", tags=["internal-budget"])


@router.get("/command-code", response_model=CommandCodeUsageList)
async def get_command_code_usage(
    session: SessionDep,
    now: NowDep,
    keys: MemberKeysDep,
    fetch: UsageFetcherDep,
) -> CommandCodeUsageList:
    """결제 기간 기준의 구성원별 사용량. 조회 기간을 받지 않고 비용 합계에도 더하지 않는다."""
    items = await command_code_usage.list_member_usage(
        session, keys=keys, fetch=fetch, now=now
    )
    return CommandCodeUsageList(items=items)
