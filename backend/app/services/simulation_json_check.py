import json
from collections.abc import Mapping
from dataclasses import dataclass

from jsonschema.exceptions import ValidationError
from jsonschema.validators import validator_for

from app.models import ValidationStatus


@dataclass(frozen=True)
class JsonCheck:
    """JSON 파싱·Schema 검증 결과. 필드 이름은 simulation_results 컬럼과 같다.

    API 호출의 성공 여부와는 별개다.
    """

    json_parse_status: ValidationStatus
    schema_validation_status: ValidationStatus
    # 빠진 필수 항목의 경로. 검사하지 않았으면 None, 검사했는데 없으면 빈 목록이다
    missing_required_fields: list[str] | None = None


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
    except json.JSONDecodeError:
        return JsonCheck(ValidationStatus.FAILED, ValidationStatus.FAILED)

    # JSON 으로 올바른 것과 Schema 를 지키는 것은 별개라서 파싱은 항상 PASSED 다
    errors = list(validator_for(schema)(schema).iter_errors(parsed))
    return JsonCheck(
        json_parse_status=ValidationStatus.PASSED,
        schema_validation_status=(
            ValidationStatus.FAILED if errors else ValidationStatus.PASSED
        ),
        missing_required_fields=_missing_required_fields(errors),
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
