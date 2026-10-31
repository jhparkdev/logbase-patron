import json

import pytest

from app.models import ValidationStatus
from app.services.simulation_json_check import (
    MAX_ERROR_MESSAGE_LENGTH,
    MAX_VALIDATION_ERRORS,
    JsonCheck,
    check_json_output,
)

V = ValidationStatus
SCHEMA = {"type": "object", "required": ["title", "price"]}


def outcome(result: JsonCheck) -> tuple[V, V, list[str] | None]:
    """판정 결과 3칸(파싱, Schema 검증, 누락 항목). 오류 상세는 따로 검사한다."""
    return (
        result.json_parse_status,
        result.schema_validation_status,
        result.missing_required_fields,
    )


@pytest.mark.parametrize("text", [None, "", "일반 문장 응답", '{"title": "a"}'])
def test_no_schema_means_not_applicable(text: str | None) -> None:
    # Schema를 지정하지 않은 테스트는 응답 내용과 상관없이 "미적용"이다
    assert check_json_output(text, None) == JsonCheck(
        V.NOT_APPLICABLE, V.NOT_APPLICABLE
    )


def test_no_response_means_not_executed_not_failed() -> None:
    # 응답을 받지 못해 검증하지 않은 것은 "검증 실패"가 아니다
    assert check_json_output(None, SCHEMA) == JsonCheck(V.NOT_EXECUTED, V.NOT_EXECUTED)


@pytest.mark.parametrize(
    "text",
    [
        "일반 문장 응답",
        "",
        '{"title": "a", "price": 1',  # 닫는 괄호 누락
        '```json\n{"title": "a", "price": 1}\n```',  # 코드 블록으로 감싼 응답
    ],
)
def test_unparseable_response_fails_both_checks(text: str) -> None:
    assert outcome(check_json_output(text, SCHEMA)) == (V.FAILED, V.FAILED, None)


def test_parsed_response_that_follows_schema_passes() -> None:
    result = check_json_output('{"title": "a", "price": 1}', SCHEMA)
    assert result == JsonCheck(V.PASSED, V.PASSED, missing_required_fields=[])


def test_parsed_response_missing_required_field_fails_schema_only() -> None:
    # T-22: 파싱은 성공했지만 필수 항목이 빠졌다. 결과를 따로 기록한다
    result = check_json_output('{"title": "a"}', SCHEMA)
    assert outcome(result) == (V.PASSED, V.FAILED, ["price"])


def test_missing_fields_are_listed_in_sorted_order() -> None:
    schema = {"type": "object", "required": ["title", "price", "category"]}
    result = check_json_output('{"title": "a"}', schema)
    assert result.missing_required_fields == ["category", "price"]


def test_parsed_response_with_wrong_type_is_not_a_missing_field() -> None:
    # 항목은 있는데 타입이 틀린 것은 "누락"이 아니다
    schema = {"type": "object", "properties": {"price": {"type": "integer"}}}
    result = check_json_output('{"price": "비쌈"}', schema)
    assert outcome(result) == (V.PASSED, V.FAILED, [])


def test_valid_json_of_different_top_level_type_is_not_a_missing_field() -> None:
    # 객체를 요구했는데 배열로 답했다. JSON으로는 올바르고, 빠진 항목을 따질 대상도 아니다
    assert outcome(check_json_output("[1, 2]", SCHEMA)) == (V.PASSED, V.FAILED, [])


def test_nested_missing_field_is_reported_with_its_path() -> None:
    schema = {
        "type": "object",
        "properties": {"item": {"type": "object", "required": ["price"]}},
    }
    result = check_json_output('{"item": {}}', schema)
    assert result.missing_required_fields == ["item.price"]


def test_array_element_missing_field_is_reported_with_its_path() -> None:
    schema = {
        "type": "object",
        "properties": {
            "items": {"type": "array", "items": {"type": "object", "required": ["id"]}}
        },
    }
    result = check_json_output('{"items": [{"id": 1}, {}]}', schema)
    assert result.missing_required_fields == ["items.1.id"]


def test_missing_field_is_reported_even_when_another_rule_also_fails() -> None:
    schema = {
        "type": "object",
        "required": ["title"],
        "properties": {"price": {"type": "integer"}},
    }
    result = check_json_output('{"price": "비쌈"}', schema)
    assert outcome(result) == (V.PASSED, V.FAILED, ["title"])


def test_missing_fields_are_not_judged_when_nothing_was_checked() -> None:
    # 미적용·미실행·파싱 실패에서는 누락 목록을 만들지 않는다(None)
    assert check_json_output(None, None).missing_required_fields is None
    assert check_json_output(None, SCHEMA).missing_required_fields is None
    assert check_json_output("일반 문장", SCHEMA).missing_required_fields is None


# --- 검증 오류 상세(validation_errors): 왜 실패했는지 알려 주는 부가 정보 ---
# 모양은 DB 담당 seed 와 같다: {"errors": ["문장", ...]} (여기에 잘렸는지 표시 truncated 를 더한다)


def error_lines(result: JsonCheck) -> list[str]:
    assert result.validation_errors is not None
    return result.validation_errors["errors"]


@pytest.mark.parametrize(
    "text, schema",
    [
        ("일반 문장", None),  # 미적용
        (None, SCHEMA),  # 미실행
        ('{"title": "a", "price": 1}', SCHEMA),  # 통과
    ],
)
def test_no_error_details_when_nothing_failed(
    text: str | None, schema: dict[str, object] | None
) -> None:
    # 실패하지 않았으면 빈 객체가 아니라 None 이다 (missing_required_fields 와 같은 원칙)
    assert check_json_output(text, schema).validation_errors is None


def test_unparseable_response_reports_one_json_parse_error() -> None:
    result = check_json_output("일반 문장 응답", SCHEMA)

    [line] = error_lines(result)
    assert line.startswith("JSON 파싱 실패: Expecting value")
    assert result.validation_errors is not None
    assert result.validation_errors["truncated"] is False


def test_schema_violation_is_one_sentence_with_its_path() -> None:
    schema = {"type": "object", "properties": {"price": {"type": "integer"}}}

    assert check_json_output('{"price": "비쌈"}', schema).validation_errors == {
        "errors": ["price: '비쌈' is not of type 'integer'"],
        "truncated": False,
    }


def test_error_path_uses_dots_like_missing_required_fields() -> None:
    schema = {
        "type": "object",
        "properties": {
            "items": {
                "type": "array",
                "items": {"type": "object", "properties": {"id": {"type": "integer"}}},
            }
        },
    }

    assert error_lines(check_json_output('{"items": [{"id": "x"}]}', schema)) == [
        "items.0.id: 'x' is not of type 'integer'"
    ]


def test_whole_document_error_has_no_path_prefix() -> None:
    assert error_lines(check_json_output('{"title": "a"}', SCHEMA)) == [
        "'price' is a required property"
    ]


def test_errors_are_listed_in_path_order() -> None:
    schema = {
        "type": "object",
        "properties": {"b": {"type": "integer"}, "a": {"type": "integer"}},
    }

    lines = error_lines(check_json_output('{"b": "x", "a": "y"}', schema))

    assert [line.split(":")[0] for line in lines] == ["a", "b"]


# 개수 상한은 바로 전, 정확히 그 값, 바로 후를 모두 검사한다
@pytest.mark.parametrize(
    "count, truncated",
    [
        (MAX_VALIDATION_ERRORS - 1, False),
        (MAX_VALIDATION_ERRORS, False),
        (MAX_VALIDATION_ERRORS + 1, True),
        (MAX_VALIDATION_ERRORS * 3, True),
    ],
)
def test_error_count_is_capped_and_marked_truncated(
    count: int, truncated: bool
) -> None:
    names = [f"p{index:03d}" for index in range(count)]
    schema = {
        "type": "object",
        "properties": {name: {"type": "integer"} for name in names},
    }
    text = json.dumps({name: "x" for name in names})

    result = check_json_output(text, schema)

    assert result.validation_errors is not None
    assert result.validation_errors["truncated"] is truncated
    kept = [line.split(":")[0] for line in error_lines(result)]
    assert kept == names[: min(count, MAX_VALIDATION_ERRORS)]


def test_long_message_is_shortened_to_the_limit() -> None:
    # 모델이 돌려준 값이 메시지에 그대로 들어가므로 한 문장의 길이를 제한한다
    schema = {"type": "object", "properties": {"price": {"type": "integer"}}}
    text = json.dumps({"price": "가" * (MAX_ERROR_MESSAGE_LENGTH * 3)})

    [line] = error_lines(check_json_output(text, schema))

    assert len(line) == MAX_ERROR_MESSAGE_LENGTH
    assert line.endswith("…")


def test_error_details_can_be_stored_as_json() -> None:
    # simulation_results.validation_errors 는 JSONB 라서 JSON 으로 직렬화되어야 한다
    schema = {"type": "object", "properties": {"price": {"type": "integer"}}}
    result = check_json_output('{"price": "비쌈"}', schema)

    assert json.loads(json.dumps(result.validation_errors)) == result.validation_errors
