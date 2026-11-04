from app.schemas.assistant import SimulatorPatch, SimulatorState
from app.services.assistant_settings import merge_settings


def test_partial_settings_do_not_erase_prompt_models_or_other_parameters() -> None:
    current = SimulatorState(
        prompt_text="keep", execution_config={"temperature": 0.3, "max_tokens": 512}
    )
    merged = merge_settings(
        current, SimulatorPatch(execution_config={"max_tokens": 2048})
    )
    assert merged.prompt_text == "keep"
    assert merged.execution_config.temperature == 0.3
    assert merged.execution_config.max_tokens == 2048
    assert current.execution_config.max_tokens == 512


def test_explicit_null_clears_only_requested_parameter() -> None:
    current = SimulatorState(execution_config={"temperature": 0.3, "max_tokens": 512})
    merged = merge_settings(
        current, SimulatorPatch(execution_config={"max_tokens": None})
    )
    assert merged.execution_config.max_tokens is None
    assert merged.execution_config.temperature == 0.3
