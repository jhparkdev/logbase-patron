"""Pydantic 계약에서 로컬 모델이 읽기 쉬운 도구 스키마를 만든다."""

from typing import Any

from pydantic import BaseModel

from app.schemas.simulation import ExecutionConfig


def _inline(
    value: Any, definitions: dict[str, Any], seen: frozenset[str] = frozenset()
) -> Any:
    if isinstance(value, list):
        return [_inline(item, definitions, seen) for item in value]
    if not isinstance(value, dict):
        return value
    reference = value.get("$ref")
    if reference:
        name = reference.rsplit("/", 1)[-1]
        if name in seen:
            return {}
        return _inline(definitions[name], definitions, seen | {name})
    result = {
        key: _inline(item, definitions, seen)
        for key, item in value.items()
        if key not in {"$defs", "title", "default"}
    }
    branches = result.get("anyOf", [])
    non_null = [branch for branch in branches if branch.get("type") != "null"]
    if (
        len(branches) == 2
        and len(non_null) == 1
        and isinstance(non_null[0].get("type"), str)
    ):
        result.pop("anyOf")
        base = non_null[0]
        result = {**result, **base, "type": [base["type"], "null"]}
        if "enum" in result:
            result["enum"] = [*result["enum"], None]
    return result


def parameters_for(name: str, model: type[BaseModel]) -> dict[str, Any]:
    raw = model.model_json_schema()
    definitions = raw.get("$defs", {})
    schema = _inline(raw, definitions)
    if name == "list_simulations":
        allowed = {
            "start_date",
            "end_date",
            "model_id",
            "status",
            "page",
            "simulation_id",
        }
        schema["properties"] = {
            key: value for key, value in schema["properties"].items() if key in allowed
        }
    if name == "prepare_simulator_settings":
        properties = schema["properties"]
        properties.pop("execution_config")
        properties.update(
            _inline(ExecutionConfig.model_json_schema(), definitions)["properties"]
        )
        # JSON Schema 자체는 개방 객체다. JsonValue의 재귀 정의를 도구 설명으로 보내지 않는다.
        properties["json_schema"] = {
            "type": ["object", "null"],
            "description": "표준 JSON Schema 문서. type, properties, required를 포함한다. 출력 예시 데이터가 아니다. 변경할 때만 보낸다.",
        }
        properties["models"]["type"] = "array"
        for field_schema in properties.values():
            field_schema["description"] = (
                field_schema.get("description", "")
                + " 선택사항: 이 항목을 변경할 때만 보내고, 나머지는 생략한다."
            )
        schema["additionalProperties"] = False
    return schema


def patch_arguments(arguments: dict[str, Any]) -> dict[str, Any]:
    result = dict(arguments)
    shared = {
        key: result.pop(key) for key in ExecutionConfig.model_fields if key in result
    }
    if shared:
        nested = result.get("execution_config", {})
        if not isinstance(nested, dict) or any(
            key in nested and nested[key] != value for key, value in shared.items()
        ):
            raise ValueError("공통 설정 형식이 서로 다르다")
        result["execution_config"] = {**nested, **shared}
    return result
