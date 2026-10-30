"""app/api/simulation_deps.py 테스트. 실제 OpenRouter 는 부르지 않고 연결 모양만 확인한다."""

import pytest
from pydantic import SecretStr

from app.api.simulation_deps import get_model_caller
from app.openrouter.client import OpenRouterClient

# 테스트용 가짜 Key. 오류나 출력에 드러나는지 찾을 표식으로 쓴다
FAKE_KEY = "sk-or-test-only-not-a-real-key"


def test_refuses_to_run_without_key() -> None:
    """Key 를 지운 상태에서는 실행을 받지 않는다. 의존성이 저장보다 먼저 풀려 아무것도 저장되지 않는다."""
    with pytest.raises(RuntimeError, match="OPENROUTER_API_KEY"):
        get_model_caller(None)


def test_refuses_to_run_with_empty_key() -> None:
    """.env 에 값만 지운 줄(OPENROUTER_API_KEY=)이 남아 있어도 Key 가 없는 것으로 본다."""
    with pytest.raises(RuntimeError, match="OPENROUTER_API_KEY"):
        get_model_caller(SecretStr(""))


def test_returns_call_model_of_real_client_when_key_is_set() -> None:
    caller = get_model_caller(SecretStr(FAKE_KEY))

    assert isinstance(caller.__self__, OpenRouterClient)
    assert caller.__func__ is OpenRouterClient.call_model


def test_key_is_not_exposed_in_caller_repr() -> None:
    caller = get_model_caller(SecretStr(FAKE_KEY))

    assert FAKE_KEY not in repr(caller)
    assert FAKE_KEY not in str(caller)
