import pytest

from app.services.simulation_json_check import (
    JsonCheck,
    SchemaCheck,
    check_json_output,
)

SCHEMA = {"type": "object", "required": ["title", "price"]}


@pytest.mark.parametrize("text", [None, "", "일반 문장 응답", '{"title": "a"}'])
def test_no_schema_means_not_applied(text: str | None) -> None:
    # Schema를 지정하지 않은 테스트는 응답 내용과 상관없이 "미적용"이다
    assert check_json_output(text, None) == JsonCheck(None, SchemaCheck.NOT_APPLIED)


def test_no_response_means_not_run_not_failed() -> None:
    # 응답을 받지 못해 검증하지 않은 것은 "검증 실패"가 아니다
    assert check_json_output(None, SCHEMA) == JsonCheck(None, SchemaCheck.NOT_RUN)


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
    assert check_json_output(text, SCHEMA) == JsonCheck(False, SchemaCheck.FAILED)


def test_parsed_response_that_follows_schema_passes() -> None:
    result = check_json_output('{"title": "a", "price": 1}', SCHEMA)
    assert result == JsonCheck(True, SchemaCheck.PASSED)


def test_parsed_response_missing_required_field_fails_schema_only() -> None:
    # T-22: 파싱은 성공했지만 필수 항목이 빠졌다. 두 결과를 따로 기록한다
    result = check_json_output('{"title": "a"}', SCHEMA)
    assert result == JsonCheck(True, SchemaCheck.FAILED)


def test_parsed_response_with_wrong_type_fails_schema_only() -> None:
    schema = {"type": "object", "properties": {"price": {"type": "integer"}}}
    result = check_json_output('{"price": "비쌈"}', schema)
    assert result == JsonCheck(True, SchemaCheck.FAILED)


def test_valid_json_of_different_top_level_type_fails_schema_only() -> None:
    # 객체를 요구했는데 배열로 답했다. JSON으로는 올바르다
    assert check_json_output("[1, 2]", SCHEMA) == JsonCheck(True, SchemaCheck.FAILED)
