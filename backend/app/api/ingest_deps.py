"""기록 수신 API가 쓰는 인증. 로그인 세션 대신 수신 토큰 헤더로 확인한다."""

import hmac
from typing import Annotated

from fastapi import Depends, Header, status

from app.api.deps import SettingsDep
from app.api.errors import ApiError
from app.schemas.common import ErrorCode

INGEST_TOKEN_HEADER = "X-Patron-Ingest-Token"
INGEST_TOKEN_MESSAGE = "수신 토큰이 올바르지 않습니다."


def require_ingest_token(
    settings: SettingsDep,
    token: Annotated[str | None, Header(alias=INGEST_TOKEN_HEADER)] = None,
) -> None:
    """수신 토큰이 설정과 같을 때만 통과한다. 서버에 토큰이 없으면 모두 거절한다.

    없는 경우와 틀린 경우를 구분해 알리지 않는다. 비교는 시간 차이로 값을 추측하지 못하게 한다.
    """
    expected = settings.ingest_token.get_secret_value() if settings.ingest_token else ""
    if (
        not expected
        or not token
        or not hmac.compare_digest(token.encode(), expected.encode())
    ):
        raise ApiError(
            status.HTTP_401_UNAUTHORIZED,
            ErrorCode.UNAUTHENTICATED,
            INGEST_TOKEN_MESSAGE,
        )


IngestTokenDep = Depends(require_ingest_token)
