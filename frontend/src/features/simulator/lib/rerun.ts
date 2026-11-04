import type { SimulatorFormValues } from "./form";
import { MODEL_LIMITS } from "./limits";
import type { ModelChoice, ScenarioChoice } from "./presentation";

export function restoreRerunValues(
  source: SimulatorFormValues,
  choices: ModelChoice[],
  scenarios: ScenarioChoice[],
) {
  const warnings: string[] = [];
  const comparisons = source.comparisons.map((item) => {
    const model = choices.find((choice) => choice.key === item.modelKey);
    return {
      ...item,
      modelKey: model?.selectable ? item.modelKey : "",
      settings: { ...item.settings },
    };
  });
  if (
    comparisons.some(
      (item, index) => item.modelKey !== source.comparisons[index].modelKey,
    )
  )
    warnings.push(
      "지금 고를 수 없는 모델의 비교 칸을 비웠어요. 모델을 바꾸거나 그 칸을 제거해 주세요.",
    );
  if (comparisons.filter((item) => item.modelKey).length < MODEL_LIMITS.min)
    warnings.push(`비교할 모델을 ${MODEL_LIMITS.min}개 이상 골라 주세요.`);
  const missingScenario =
    source.mode === "scenario" &&
    !scenarios.some((scenario) => scenario.key === source.scenarioKey);
  if (missingScenario)
    warnings.push(
      "지금은 시나리오를 찾을 수 없어 직접 입력으로 바꿨어요. 저장된 Prompt와 입력은 그대로예요.",
    );
  return {
    values: {
      ...source,
      files: [...source.files],
      comparisons,
      ...(missingScenario ? { mode: "custom" as const, scenarioKey: "" } : {}),
    },
    warnings,
  };
}
