"""프로젝트 등록(P-02) 경로. 입력 검증과 응답 변환만 하고, 규칙은 services/projects가 한다."""

from fastapi import APIRouter, status
from fastapi.responses import JSONResponse

from app.api.deps import CurrentUserDep
from app.db import SessionDep
from app.schemas.common import ErrorResponse
from app.schemas.project import ProjectCreate, ProjectRead
from app.schemas.project_error import (
    DUPLICATE_MESSAGE,
    ProjectDuplicateResponse,
    ProjectErrorCode,
)
from app.services import projects
from app.services.projects import ProjectDuplicateError

CREATE_ERRORS = {
    status.HTTP_409_CONFLICT: {"model": ProjectDuplicateResponse},
    status.HTTP_422_UNPROCESSABLE_CONTENT: {"model": ErrorResponse},
}

router = APIRouter(prefix="/projects", tags=["projects"])


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=ProjectRead,
    responses=CREATE_ERRORS,
)
async def create_project(
    body: ProjectCreate, session: SessionDep, user: CurrentUserDep
) -> ProjectRead | JSONResponse:
    try:
        return await projects.create_project(session, dict(body), user.user_id)
    except ProjectDuplicateError as error:
        error_body = ProjectDuplicateResponse(
            code=ProjectErrorCode.PROJECT_DUPLICATE,
            message=DUPLICATE_MESSAGE,
            existing=error.existing,
        )
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content=error_body.model_dump(mode="json"),
        )
