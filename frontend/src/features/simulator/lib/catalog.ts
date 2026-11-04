import type { components } from "../../../shared/api/schema";
import { MAX_TOKENS, TEMPERATURE } from "./limits";
import { PARAMETER_NAMES, type TuningParameter } from "./parameters";
import type { ModelChoice } from "./presentation";

type Schemas = components["schemas"];
type Model = Pick<
  Schemas["ModelRead"],
  | "model_id"
  | "display_name"
  | "provider"
  | "input_modalities"
  | "temperature_supported"
  | "reasoning_efforts"
  | "supports_json_schema"
  | "current_price"
>;

const AUTO_CHEAPEST: Schemas["AutoProvider"] = "AUTO_CHEAPEST";
const AUTO_CHEAPEST_LABEL = "가장 싼 업체 자동";
const IMAGE_MODALITY = "image";
const STRUCTURED_OUTPUT_PARAMETER = "response_format";
const KEY_SEPARATOR = ":";
const NUMERIC_ID = /^\d+$/;
const EFFORT_LABELS: Record<Schemas["ReasoningEffort"], string> = {
  none: "사용 안 함",
  minimal: "최소",
  low: "낮음",
  medium: "보통",
  high: "높음",
  xhigh: "매우 높음",
  max: "최대",
};

export function choiceKey(modelId: number, provider: string): string {
  return `${modelId}${KEY_SEPARATOR}${provider}`;
}

/** 서버 업체 이름에 구분자가 들어 있어도 첫 구분자로만 나눈다. */
export function parseChoiceKey(key: string) {
  const index = key.indexOf(KEY_SEPARATOR);
  const modelId = key.slice(0, index);
  const provider = key.slice(index + KEY_SEPARATOR.length);
  if (index < 1 || !NUMERIC_ID.test(modelId) || !provider) return undefined;
  return { model_id: Number(modelId), execution_provider: provider };
}

function tuningParameters(model: Model): TuningParameter[] {
  return [
    ...(model.temperature_supported
      ? [
          {
            key: "temperature" as const,
            kind: "number" as const,
            min: TEMPERATURE.min,
            max: TEMPERATURE.max,
            step: TEMPERATURE.step,
          },
        ]
      : []),
    // 모델 응답에 지원 여부가 없다. 백엔드도 이 값은 모델 지원 여부로 거절하지 않는다.
    {
      key: "maxTokens" as const,
      kind: "number" as const,
      min: 1,
      max: MAX_TOKENS,
      step: 1,
    },
    ...(model.reasoning_efforts.length
      ? [
          {
            key: "reasoningEffort" as const,
            kind: "choice" as const,
            options: model.reasoning_efforts.map((value) => ({
              value,
              label: EFFORT_LABELS[value],
            })),
          },
        ]
      : []),
  ];
}

/** 모델 하나를 서버 업체마다 고를 수 있는 항목으로 나누고 "가장 싼 업체 자동"을 끝에 더한다. 업체를 모르면 고를 수 없는 한 행으로 남긴다. */
export function toModelChoices(
  model: Model,
  state: { providers: readonly string[] } | { failed: true },
): ModelChoice[] {
  const parameters = tuningParameters(model);
  const base = {
    name: model.display_name,
    creator: model.provider,
    supportsImages: model.input_modalities.includes(IMAGE_MODALITY),
    tuningParameters: parameters,
    supportedParameters: [
      ...parameters.map((parameter) => PARAMETER_NAMES[parameter.key]),
      ...(model.supports_json_schema ? [STRUCTURED_OUTPUT_PARAMETER] : []),
    ],
    // 단가가 없는 모델은 price 자체를 두지 않아 화면이 미확인으로 보여 준다
    ...(model.current_price
      ? {
          price: {
            input: model.current_price.input_price_per_token,
            output: model.current_price.output_price_per_token,
          },
        }
      : {}),
  };
  const providers = "providers" in state ? state.providers : [];
  if (!providers.length)
    return [
      {
        ...base,
        key: choiceKey(model.model_id, ""),
        provider: "확인 불가",
        selectable: false,
        unavailableReason: "서버 업체를 확인할 수 없어요",
      },
    ];
  return [
    ...providers.map((provider) => ({
      ...base,
      key: choiceKey(model.model_id, provider),
      provider,
      selectable: true,
    })),
    // 서버가 접수할 때 가장 싼 업체로 정하고, 저장하는 값은 실제 업체 이름이다
    {
      ...base,
      key: choiceKey(model.model_id, AUTO_CHEAPEST),
      provider: AUTO_CHEAPEST_LABEL,
      selectable: true,
    },
  ];
}
