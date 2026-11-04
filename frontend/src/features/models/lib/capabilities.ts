import type { components } from "../../../shared/api/schema";
import { formatCount } from "../../../shared/lib/format";
import { modalitiesFlow } from "./view";

type Capabilities = Pick<
  components["schemas"]["ModelDetailRead"],
  | "input_modalities"
  | "output_modalities"
  | "supports_json_schema"
  | "supports_tools"
  | "temperature_supported"
  | "reasoning_efforts"
>;

export type CapabilityTag = {
  key: "modalities" | "json" | "tools" | "temperature" | "reasoning";
  label: string;
  supported: boolean;
};

const UNKNOWN_LABEL = "미확인";

/** 모델이 받는 기능 태그. 미지원도 빼지 않아 모델끼리 비교할 수 있게 함 */
export function capabilityTags(model: Capabilities): CapabilityTag[] {
  return [
    {
      key: "modalities",
      label: modalitiesFlow(model.input_modalities, model.output_modalities),
      supported: true,
    },
    {
      key: "json",
      label: "JSON 스키마",
      supported: model.supports_json_schema,
    },
    { key: "tools", label: "함수 호출", supported: model.supports_tools },
    {
      key: "temperature",
      label: "Temperature 조절",
      supported: model.temperature_supported,
    },
    {
      key: "reasoning",
      label: "추론 강도 조절",
      supported: model.reasoning_efforts.length > 0,
    },
  ];
}

/** 태그 묶음 제목 옆에 붙는 Context Length. 모르면 0이 아니라 미확인 */
export function contextCaption(contextLength: number | null): string {
  return `Context ${contextLength === null ? UNKNOWN_LABEL : `${formatCount(contextLength)} 토큰`}`;
}
