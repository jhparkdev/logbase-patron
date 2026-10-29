import type { SimulatorFormValues } from "./form";
import { MODEL_LIMITS } from "./limits";
import type { ModelChoice, ScenarioChoice } from "./presentation";

export function restoreRerunValues(
  source: SimulatorFormValues,
  choices: ModelChoice[],
  scenarios: ScenarioChoice[],
) {
  const warnings: string[] = [];
  const selections = source.selections.map((key) => {
    const model = choices.find((choice) => choice.key === key);
    return model?.selectable ? key : "";
  });
  if (selections.some((key, index) => key !== source.selections[index]))
    warnings.push(
      "현재 선택할 수 없는 모델의 비교 칸을 비웠어요. 모델을 교체하거나 해당 칸을 제거해 주세요.",
    );
  if (selections.filter(Boolean).length < MODEL_LIMITS.min)
    warnings.push(`비교할 모델을 ${MODEL_LIMITS.min}개 이상 선택해 주세요.`);
  const missingScenario =
    source.mode === "scenario" &&
    !scenarios.some((scenario) => scenario.key === source.scenarioKey);
  if (missingScenario)
    warnings.push(
      "현재 시나리오를 찾을 수 없어 Custom으로 전환했어요. 저장된 Prompt와 입력은 유지해요.",
    );
  return {
    values: {
      ...source,
      files: [...source.files],
      selections,
      ...(missingScenario ? { mode: "custom" as const, scenarioKey: "" } : {}),
    },
    warnings,
  };
}
