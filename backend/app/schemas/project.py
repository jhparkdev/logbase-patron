"""프로젝트 등록(P-02) 요청·응답 모델."""

from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints

from app.models import ProjectType
from app.schemas.subscription import ShortText

PROJECT_CODE_MAX_LENGTH = 50
# 영문 대문자·숫자·밑줄·하이픈. 고객·서비스 코드와 같은 모양이다
ProjectCode = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=PROJECT_CODE_MAX_LENGTH,
        pattern=r"^[A-Z0-9][A-Z0-9_-]*$",
    ),
]


class ProjectCreate(BaseModel):
    """프로젝트 등록. 이름이 같은 사용 중 프로젝트가 있으면 만들지 않는다(띄어쓰기·대소문자 무시)."""

    model_config = ConfigDict(extra="forbid")

    name: ShortText
    # 화면은 보내지 않는다. 보내지 않으면 내부 개발로 저장한다
    project_type: ProjectType = ProjectType.INTERNAL_DEV
    # 없으면 서버가 프로젝트 번호로 만든다
    project_code: ProjectCode | None = None


class ProjectRead(BaseModel):
    project_id: int
    project_code: str
    name: str
    project_type: ProjectType
