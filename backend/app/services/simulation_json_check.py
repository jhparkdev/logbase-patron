import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import TypedDict

from jsonschema.exceptions import ValidationError
from jsonschema.validators import validator_for

from app.models import ValidationStatus

# 위반이 수백 개이거나 모델이 돌려준 값이 길어도 저장·응답 크기가 커지지 않게 제한한다
MAX_VALIDATION_ERRORS = 20
MAX_ERROR_MESSAGE_LENGTH = 200
ELLIPSIS = "…"


class ValidationErrors(TypedDict):
    """simulation_results.validation_errors 에 저장하는 모양.

    errors 는 DB 담당 seed 와 같은 문장 목록이다. truncated 는 상한을 넘어 앞의 일부만 담았다는 표시다.
    """

    errors: list[str]
    truncated: bool


@dataclass(frozen=True)
class JsonCheck:
    """JSON 파싱·Schema 검증 결과. 필드 이름은 simulation_results 컬럼과 같다.

    API 호출의 성공 여부와는 별개다.
    """

    json_parse_status: ValidationStatus
    schema_validation_status: ValidationStatus
    # 빠진 필수 항목의 경로. 검사하지 않았으면 None, 검사했는데 없으면 빈 목록이다
    missing_required_fields: list[str] | None = None
    # 실패 이유 상세. 통과·미적용·미실행이면 빈 객체가 아니라 None 이다
    validation_errors: ValidationErrors | None = None


def check_json_output(
    response_text: str | None, schema: Mapping[str, object] | None
) -> JsonCheck:
    """모델 응답이 JSON이고 지정한 Schema를 지키는지 검사한다. 원문은 바꾸지 않는다."""
    if schema is None:
        return JsonCheck(
            ValidationStatus.NOT_APPLICABLE, ValidationStatus.NOT_APPLICABLE
        )
    if response_text is None:
        return JsonCheck(ValidationStatus.NOT_EXECUTED, ValidationStatus.NOT_EXECUTED)

    try:
        parsed = json.loads(response_text)
    except json.JSONDecodeError as error:
        return JsonCheck(
            ValidationStatus.FAILED,
            ValidationStatus.FAILED,
            validation_errors=_validation_errors([f"JSON 파싱 실패: {error}"]),
        )

    # JSON 으로 올바른 것과 Schema 를 지키는 것은 별개라서 파싱은 항상 PASSED 다
    errors = list(validator_for(schema)(schema).iter_errors(parsed))
    return JsonCheck(
        json_parse_status=ValidationStatus.PASSED,
        schema_validation_status=(
            ValidationStatus.FAILED if errors else ValidationStatus.PASSED
        ),
        missing_required_fields=_missing_required_fields(errors),
        validation_errors=_schema_errors(errors),
    )


def _missing_required_fields(errors: list[ValidationError]) -> list[str]:
    missing: set[str] = set()
    for error in errors:
        if error.validator != "required":
            continue
        parent = [str(part) for part in error.absolute_path]
        missing.update(
            ".".join([*parent, name])
            for name in error.validator_value
            if name not in error.instance
        )
    return sorted(missing)


def _schema_errors(errors: list[ValidationError]) -> ValidationErrors | None:
    if not errors:
        return None
    # 같은 응답이면 같은 순서로 저장되도록 (경로, 규칙) 순으로 정렬한 뒤 상한만큼 자른다
    keyed = sorted(
        (
            ".".join(str(part) for part in error.absolute_path),
            str(error.validator),
            error.message,
        )
        for error in errors
    )
    return _validation_errors([_sentence(path, message) for path, _, message in keyed])


def _sentence(path: str, message: str) -> str:
    # 경로는 missing_required_fields 와 같은 점 표기. 문서 전체에 대한 오류는 경로 없이 문장만 쓴다
    return f"{path}: {message}" if path else message


def _shorten(sentence: str) -> str:
    if len(sentence) <= MAX_ERROR_MESSAGE_LENGTH:
        return sentence
    return sentence[: MAX_ERROR_MESSAGE_LENGTH - len(ELLIPSIS)] + ELLIPSIS


def _validation_errors(sentences: list[str]) -> ValidationErrors:
    return {
        "errors": [
            _shorten(sentence) for sentence in sentences[:MAX_VALIDATION_ERRORS]
        ],
        "truncated": len(sentences) > MAX_VALIDATION_ERRORS,
    }
