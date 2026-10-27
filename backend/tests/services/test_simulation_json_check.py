import pytest

from app.services.simulation_json_check import (
    JsonCheck,
    ValidationStatus,
    check_json_output,
)

V = ValidationStatus
SCHEMA = {"type": "object", "required": ["title", "price"]}


def test_status_values_match_the_db_enum() -> None:
    # models.py 의 ValidationStatus 와 값이 같아야 DB 제약에 걸리지 않는다
    assert {status.value for status in ValidationStatus} == {
        "PASSED",
        "FAILED",
        "NOT_APPLICABLE",
        "NOT_EXECUTED",
    }


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
    assert check_json_output(text, SCHEMA) == JsonCheck(V.FAILED, V.FAILED)


def test_parsed_response_that_follows_schema_passes() -> None:
    result = check_json_output('{"title": "a", "price": 1}', SCHEMA)
    assert result == JsonCheck(V.PASSED, V.PASSED, missing_required_fields=[])


def test_parsed_response_missing_required_field_fails_schema_only() -> None:
    # T-22: 파싱은 성공했지만 필수 항목이 빠졌다. 결과를 따로 기록한다
    result = check_json_output('{"title": "a"}', SCHEMA)
    assert result == JsonCheck(V.PASSED, V.FAILED, missing_required_fields=["price"])


def test_missing_fields_are_listed_in_sorted_order() -> None:
    schema = {"type": "object", "required": ["title", "price", "category"]}
    result = check_json_output('{"title": "a"}', schema)
    assert result.missing_required_fields == ["category", "price"]


def test_parsed_response_with_wrong_type_is_not_a_missing_field() -> None:
    # 항목은 있는데 타입이 틀린 것은 "누락"이 아니다
    schema = {"type": "object", "properties": {"price": {"type": "integer"}}}
    result = check_json_output('{"price": "비쌈"}', schema)
    assert result == JsonCheck(V.PASSED, V.FAILED, missing_required_fields=[])


def test_valid_json_of_different_top_level_type_is_not_a_missing_field() -> None:
    # 객체를 요구했는데 배열로 답했다. JSON으로는 올바르고, 빠진 항목을 따질 대상도 아니다
    assert check_json_output("[1, 2]", SCHEMA) == JsonCheck(
        V.PASSED, V.FAILED, missing_required_fields=[]
    )


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
    assert result == JsonCheck(V.PASSED, V.FAILED, missing_required_fields=["title"])


def test_missing_fields_are_not_judged_when_nothing_was_checked() -> None:
    # 미적용·미실행·파싱 실패에서는 누락 목록을 만들지 않는다(None)
    assert check_json_output(None, None).missing_required_fields is None
    assert check_json_output(None, SCHEMA).missing_required_fields is None
    assert check_json_output("일반 문장", SCHEMA).missing_required_fields is None
