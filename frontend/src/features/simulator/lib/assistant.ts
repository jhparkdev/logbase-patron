import type { components } from "../../../shared/api/schema";
import type { AssistantPatch } from "../../../shared/lib/assistant";
import { choiceKey, parseChoiceKey } from "./catalog";
import { createComparison, hasCustomComparison } from "./comparisons";
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

/** 공통값을 실제 값으로 바꾸는 패치인지. 값을 지우기만 하는 패치는 공통 설정을 켜지 않는다. */
function setsCommonValue(patch: AssistantPatch) {
  return Object.values(patch.execution_config ?? {}).some(
    (value) => value != null,
  );
}

export function applyAssistantPatch(
  current: SimulatorFormValues,
  patch: AssistantPatch,
): SimulatorFormValues {
  const turningOn = setsCommonValue(patch) && !current.commonEnabled;
  // 꺼진 동안 칸에 남은 값이 함께 켜지면 요청하지 않은 설정까지 실행에 들어가므로 비운다.
  const next = turningOn
    ? { ...current, temperature: "", maxTokens: "", reasoningEffort: "" }
    : { ...current };
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
  // 실행은 공통 설정을 켰을 때만 공통값을 쓴다(request.ts). 바꾼 값이 실제로 쓰이도록 함께 켠다.
  // 화면과 같이 모델별 설정과는 함께 쓰지 않는다. 둘이 겹치면 assistantPatchIssue가 거절한다.
  if (setsCommonValue(patch)) next.commonEnabled = true;
  else if (hasCustomComparison(next.comparisons)) next.commonEnabled = false;
  return next;
}

export function simulatorAssistantState(
  values: SimulatorFormValues,
): Schemas["SimulatorState"] {
  // 꺼진 공통값은 실행에 쓰이지 않으므로 도우미에게도 비어 있는 것으로 보여 준다.
  const common: Schemas["ExecutionConfig"] = values.commonEnabled
    ? {
        temperature: simulatorFormSchema.shape.temperature.parse(
          values.temperature,
        ),
        max_tokens: simulatorFormSchema.shape.maxTokens.parse(values.maxTokens),
        reasoning_effort: parseEffort(values.reasoningEffort),
      }
    : {};
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
    execution_config: common,
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
  if (values.commonEnabled && hasCustomComparison(values.comparisons))
    return "모델별 설정을 쓰는 비교 항목이 있어 공통 설정을 바꿀 수 없어요. 모델별 설정을 해제한 뒤 다시 요청해 주세요.";
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
