import type { components } from "../../../shared/api/schema";
import type { AssistantPatch } from "../../../shared/lib/assistant";
import { choiceKey, parseChoiceKey } from "./catalog";
import { createComparison } from "./comparisons";
import {
  type SimulatorFormValues,
  simulatorFormSchema,
  simulatorSchemaFor,
} from "./form";
import type { ModelChoice, ScenarioChoice } from "./presentation";
import { selectionIssues } from "./presentation";

type Schemas = components["schemas"];

export function simulatorRevision(values: SimulatorFormValues) {
  return JSON.stringify({
    ...values,
    files: values.files.map((file) => [
      file.name,
      file.size,
      file.lastModified,
    ]),
  });
}

export function applyAssistantPatch(
  current: SimulatorFormValues,
  patch: AssistantPatch,
): SimulatorFormValues {
  const next = { ...current };
  if ("prompt_text" in patch) next.prompt = patch.prompt_text ?? "";
  if ("input_text" in patch) next.text = patch.input_text ?? "";
  if ("json_schema" in patch)
    next.jsonSchema =
      patch.json_schema == null
        ? ""
        : JSON.stringify(patch.json_schema, null, 2);
  if ("execution_config" in patch) {
    const config = patch.execution_config;
    if (config == null || "temperature" in config)
      next.temperature = config?.temperature?.toString() ?? "";
    if (config == null || "max_tokens" in config)
      next.maxTokens = config?.max_tokens?.toString() ?? "";
    if (config == null || "reasoning_effort" in config)
      next.reasoningEffort = config?.reasoning_effort ?? "";
  }
  if (patch.models)
    next.comparisons = patch.models.map((item) => ({
      ...createComparison(choiceKey(item.model_id, item.execution_provider)),
      settings: {
        mode: Object.values(item.execution_config ?? {}).some(
          (value) => value != null,
        )
          ? "custom"
          : "shared",
        temperature: item.execution_config?.temperature?.toString() ?? "",
        maxTokens: item.execution_config?.max_tokens?.toString() ?? "",
        reasoningEffort: item.execution_config?.reasoning_effort ?? "",
      },
    }));
  return next;
}

export function simulatorAssistantState(
  values: SimulatorFormValues,
): Schemas["SimulatorState"] {
  const temperature = simulatorFormSchema.shape.temperature.parse(
    values.temperature,
  );
  const maxTokens = simulatorFormSchema.shape.maxTokens.parse(values.maxTokens);
  const effort = values.reasoningEffort;
  const models = values.comparisons
    .filter((item) => item.modelKey)
    .map((item) => {
      const model = parseChoiceKey(item.modelKey);
      if (!model) throw new Error("선택한 모델을 다시 확인해 주세요.");
      const config: Schemas["ExecutionConfig"] =
        item.settings.mode === "custom"
          ? {
              temperature: simulatorFormSchema.shape.temperature.parse(
                item.settings.temperature,
              ),
              max_tokens: simulatorFormSchema.shape.maxTokens.parse(
                item.settings.maxTokens,
              ),
              reasoning_effort: parseEffort(item.settings.reasoningEffort),
            }
          : {};
      return { ...model, execution_config: config };
    });
  return {
    prompt_text: values.prompt,
    input_text: values.text || null,
    json_schema: values.jsonSchema.trim()
      ? JSON.parse(values.jsonSchema)
      : null,
    execution_config: {
      temperature,
      max_tokens: maxTokens,
      reasoning_effort: parseEffort(effort),
    },
    models,
    scenario_id: values.mode === "scenario" ? Number(values.scenarioKey) : null,
    has_images: values.files.length + values.existingAssetIds.length > 0,
  };
}

function parseEffort(value: string): Schemas["ReasoningEffort"] | undefined {
  if (!value) return undefined;
  const efforts: Schemas["ReasoningEffort"][] = [
    "none",
    "minimal",
    "low",
    "medium",
    "high",
    "xhigh",
    "max",
  ];
  const found = efforts.find((effort) => effort === value);
  if (!found) throw new Error("추론 강도를 다시 선택해 주세요.");
  return found;
}

export function assistantPatchIssue(
  values: SimulatorFormValues,
  choices: ModelChoice[],
  scenarios: ScenarioChoice[],
) {
  if (
    values.comparisons.length &&
    values.comparisons.some(
      (item) =>
        !choices.some(
          (choice) => choice.key === item.modelKey && choice.selectable,
        ),
    )
  )
    return "현재 선택할 수 없는 모델이 있어요. 다시 요청해 주세요.";
  // 빈 폼에서도 설정을 준비할 수 있으므로 필수 Prompt와 모델 수는 실행 때 검사한다.
  try {
    simulatorAssistantState(values);
  } catch {
    return "현재 입력값을 확인한 뒤 다시 요청해 주세요.";
  }
  if (!values.comparisons.length) return undefined;
  const checked = simulatorSchemaFor(choices).safeParse({
    ...values,
    prompt: values.prompt || "검증",
  });
  if (!checked.success)
    return "요청한 설정을 적용할 수 없어요. 입력값을 다시 확인해 주세요.";
  return selectionIssues(checked.data, choices, scenarios)[0];
}
