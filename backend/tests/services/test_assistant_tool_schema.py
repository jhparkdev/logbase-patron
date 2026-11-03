import json

from app.schemas.assistant import SimulatorPatch
from app.services.assistant_tool_schema import parameters_for, patch_arguments
from app.services.assistant_tools import HistoryQuery


def test_setting_tool_uses_direct_parameters_with_original_contract_limits() -> None:
    schema = parameters_for("prepare_simulator_settings", SimulatorPatch)
    assert "$ref" not in json.dumps(schema)
    assert "execution_config" not in schema["properties"]
    assert schema["properties"]["max_tokens"]["maximum"] == 4096
    assert schema["properties"]["max_tokens"]["minimum"] == 1
    assert "default" not in schema["properties"]["max_tokens"]
    item = schema["properties"]["models"]["items"]
    assert item["properties"]["execution_config"]["type"] == "object"


def test_direct_parameters_preserve_explicit_clear_and_map_to_api_contract() -> None:
    parsed = SimulatorPatch.model_validate(
        patch_arguments({"max_tokens": 2048, "temperature": None})
    )
    assert parsed.model_dump(exclude_unset=True) == {
        "execution_config": {"max_tokens": 2048, "temperature": None}
    }


def test_history_page_size_is_fixed_and_not_a_model_argument() -> None:
    schema = parameters_for("list_simulations", HistoryQuery)
    assert "page_size" not in schema["properties"]
    assert HistoryQuery().page_size == 5
