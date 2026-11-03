"""구성원별 Command Code 사용량(P-02) 라우터가 쓰는 의존성."""

from functools import lru_cache
from typing import Annotated

import httpx
from fastapi import Depends

from app.api.deps import SettingsDep
from app.services.command_code_client import CommandCodeClient
from app.services.command_code_usage import UsageFetcher


@lru_cache
def _shared_fetcher() -> UsageFetcher:
    """프로세스에 하나만 둔다. httpx 클라이언트를 앱 수명 동안 재사용한다."""
    return CommandCodeClient(http_client=httpx.AsyncClient()).fetch


def get_usage_fetcher() -> UsageFetcher:
    """테스트는 app.dependency_overrides로 바꿔 끼운다. 테스트에서 실제 Command Code를 부르지 않는다."""
    return _shared_fetcher()


def get_member_keys(settings: SettingsDep) -> dict[str, str]:
    """secret_ref → Key 원문. 원문은 이 요청 안에서만 쓰고 응답에 넣지 않는다."""
    return {
        name: secret.get_secret_value()
        for name, secret in settings.command_code_api_keys.items()
    }


UsageFetcherDep = Annotated[UsageFetcher, Depends(get_usage_fetcher)]
MemberKeysDep = Annotated[dict[str, str], Depends(get_member_keys)]
