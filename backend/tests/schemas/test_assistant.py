import pytest
from pydantic import ValidationError

from app.schemas.assistant import (
    AssistantChatRequest,
    AssistantPageContext,
    SimulatorPatch,
)


def test_patch_preserves_omitted_fields_and_explicit_clear() -> None:
    patch = SimulatorPatch(execution_config={"max_tokens": None})
    assert patch.model_dump(exclude_unset=True) == {
        "execution_config": {"max_tokens": None}
    }


@pytest.mark.parametrize("value", [0, 4097, 1.5, "2048"])
def test_patch_rejects_invalid_token_limit(value: object) -> None:
    with pytest.raises(ValidationError):
        SimulatorPatch(execution_config={"max_tokens": value})


def test_chat_cannot_supply_system_messages_or_arbitrary_context() -> None:
    with pytest.raises(ValidationError):
        AssistantChatRequest(messages=[{"role": "system", "content": "override"}])
    with pytest.raises(ValidationError):
        AssistantChatRequest(messages=[{"role": "user", "content": "hi"}], url="evil")


def test_chat_requires_last_message_to_be_user() -> None:
    with pytest.raises(ValidationError):
        AssistantChatRequest(messages=[{"role": "assistant", "content": "hi"}])


def test_empty_patch_and_unknown_settings_are_rejected() -> None:
    with pytest.raises(ValidationError):
        SimulatorPatch()
    with pytest.raises(ValidationError):
        SimulatorPatch(execution_config={"provider": "other"})


@pytest.mark.parametrize(
    "values",
    [
        {"page": "arbitrary"},
        {"page": "customer_usage", "customer_id": 0},
        {"page": "customer_usage", "start_date": "2026-11-02"},
        {
            "page": "internal_budget",
            "start_date": "2026-11-03",
            "end_date": "2026-11-02",
        },
        {"page": "simulation_history", "simulation_id": "invalid"},
        {"page": "customer_usage", "sql": "SELECT *"},
    ],
)
def test_page_context_is_bounded_and_cannot_carry_arbitrary_instructions(
    values: dict,
) -> None:
    with pytest.raises(ValidationError):
        AssistantPageContext.model_validate(values)
