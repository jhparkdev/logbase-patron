import type { components } from "../../../shared/api/schema";
import type { ScenarioChoice } from "./presentation";

type Scenario = components["schemas"]["ScenarioRead"];

const JSON_INDENT = 2;

function numberOrNothing(value: unknown) {
  return typeof value === "number" ? value : undefined;
}

export function toScenarioChoice(scenario: Scenario): ScenarioChoice {
  const config = scenario.default_execution_config;
  const effort = config.reasoning_effort;
  return {
    key: String(scenario.scenario_id),
    name: scenario.name,
    prompt: scenario.prompt_template,
    imageRequired: scenario.input_type !== "TEXT",
    schemaText: scenario.default_json_schema
      ? JSON.stringify(scenario.default_json_schema, null, JSON_INDENT)
      : "",
    defaults: {
      temperature: numberOrNothing(config.temperature),
      maxTokens: numberOrNothing(config.max_tokens),
      reasoningEffort: typeof effort === "string" ? effort : undefined,
    },
  };
}

/** 재실행은 지금 비활성인 원본 시나리오로도 돌릴 수 있다. 다른 비활성 시나리오는 고르지 못하게 뺀다. */
export function restorableScenarios(
  scenarios: readonly Scenario[],
  sourceId: number | null,
): ScenarioChoice[] {
  return scenarios
    .filter((item) => item.is_active || item.scenario_id === sourceId)
    .map(toScenarioChoice);
}
