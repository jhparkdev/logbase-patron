import json
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum

from jsonschema.validators import validator_for


class SchemaCheck(StrEnum):
    PASSED = "PASSED"
    FAILED = "FAILED"
    NOT_APPLIED = "NOT_APPLIED"
    NOT_RUN = "NOT_RUN"


@dataclass(frozen=True)
class JsonCheck:
    """JSON 파싱 결과와 Schema 검증 결과. API 호출의 성공 여부와는 별개다."""

    json_valid: bool | None
    schema_check: SchemaCheck


def check_json_output(
    response_text: str | None, schema: Mapping[str, object] | None
) -> JsonCheck:
    """모델 응답이 JSON이고 지정한 Schema를 지키는지 검사한다. 원문은 바꾸지 않는다."""
    if schema is None:
        return JsonCheck(json_valid=None, schema_check=SchemaCheck.NOT_APPLIED)
    if response_text is None:
        return JsonCheck(json_valid=None, schema_check=SchemaCheck.NOT_RUN)

    try:
        parsed = json.loads(response_text)
    except json.JSONDecodeError:
        return JsonCheck(json_valid=False, schema_check=SchemaCheck.FAILED)

    # JSON 으로 올바른 것과 Schema 를 지키는 것은 별개라서 json_valid 는 항상 True 다
    follows_schema = validator_for(schema)(schema).is_valid(parsed)
    return JsonCheck(
        json_valid=True,
        schema_check=SchemaCheck.PASSED if follows_schema else SchemaCheck.FAILED,
    )
