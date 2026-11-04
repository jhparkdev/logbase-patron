"""고객 서비스 호출 기록 수신 경로. 고객 서비스가 OpenRouter 호출을 마칠 때마다 한 건씩 보낸다.

로그인 세션과 Origin 검사 없이 수신 토큰 헤더만 확인한다(main.py에서 따로 등록). 프롬프트·답변은
받지 않는다. 규격은 docs/USAGE-RECORDS.md 에 있다.
"""

from fastapi import APIRouter, Response, status

from app.api.errors import ApiError
from app.api.ingest_deps import IngestTokenDep
from app.db import SessionDep
from app.schemas.common import ErrorCode, ErrorResponse
from app.schemas.usage_record import UsageRecordCreate, UsageRecordReceipt
from app.services import usage_records

router = APIRouter(
    prefix="/usage-records", tags=["usage-records"], dependencies=[IngestTokenDep]
)

KEY_NOT_FOUND_MESSAGE = "등록되지 않은 Key입니다. key_id 를 확인해 주세요."
KEY_UNUSABLE_MESSAGE = (
    "서비스가 연결되지 않은 Key입니다. Patron 담당자에게 알려 주세요."
)
CUSTOMER_MISMATCH_MESSAGE = "customer_code 가 Key에 연결된 고객과 맞지 않습니다."
CONFLICT_MESSAGE = "이 OpenRouter 응답 id 는 다른 요청 ID의 기록에 이미 쓰였습니다."


@router.post(
    "",
    response_model=UsageRecordReceipt,
    status_code=status.HTTP_201_CREATED,
    responses={
        status.HTTP_200_OK: {
            "model": UsageRecordReceipt,
            "description": "같은 요청 ID가 이미 저장되어 있어 새로 저장하지 않았다.",
        },
        status.HTTP_401_UNAUTHORIZED: {"model": ErrorResponse},
        status.HTTP_409_CONFLICT: {"model": ErrorResponse},
        status.HTTP_422_UNPROCESSABLE_CONTENT: {"model": ErrorResponse},
    },
)
async def create_usage_record(
    record: UsageRecordCreate, session: SessionDep, response: Response
) -> UsageRecordReceipt:
    """호출 기록 한 건을 저장한다. 같은 request_id 로 다시 보내면 200으로 답하고 저장하지 않는다."""
    try:
        receipt = await usage_records.save_usage_record(session, record)
    except usage_records.UsageRecordKeyNotFoundError:
        raise _rejected(KEY_NOT_FOUND_MESSAGE) from None
    except usage_records.UsageRecordKeyUnusableError:
        raise _rejected(KEY_UNUSABLE_MESSAGE) from None
    except usage_records.UsageRecordCustomerMismatchError:
        raise _rejected(CUSTOMER_MISMATCH_MESSAGE) from None
    except usage_records.UsageRecordConflictError:
        raise ApiError(
            status.HTTP_409_CONFLICT, ErrorCode.BAD_REQUEST, CONFLICT_MESSAGE
        ) from None
    if not receipt.stored:
        response.status_code = status.HTTP_200_OK
    return receipt


def _rejected(message: str) -> ApiError:
    return ApiError(
        status.HTTP_422_UNPROCESSABLE_CONTENT, ErrorCode.VALIDATION_ERROR, message
    )
