"""프로젝트 등록(P-02) API의 오류 코드와 문구."""

from enum import StrEnum

from app.schemas.common import ErrorResponse
from app.schemas.project import ProjectRead


class ProjectErrorCode(StrEnum):
    """프론트엔드는 이 값으로 상황별로 화면을 나눈다."""

    # 같은 이름(또는 같은 코드)의 프로젝트가 이미 있음
    PROJECT_DUPLICATE = "PROJECT_DUPLICATE"


DUPLICATE_MESSAGE = "이미 있는 프로젝트입니다. 목록에서 선택해 주세요."


class ProjectDuplicateResponse(ErrorResponse):
    """409 본문. 화면이 새로 만들지 않고 기존 프로젝트를 바로 고를 수 있게 기존 행을 함께 준다."""

    code: ProjectErrorCode
    existing: ProjectRead
