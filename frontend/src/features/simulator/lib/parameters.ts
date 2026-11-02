export type ParameterKey = "temperature" | "maxTokens" | "reasoningEffort";
export type TuningParameter =
  | {
      key: "temperature" | "maxTokens";
      kind: "number";
      min: number;
      max: number;
      step: number;
    }
  | {
      key: "reasoningEffort";
      kind: "choice";
      options: readonly { value: string; label: string }[];
    };

export const PARAMETER_LABELS: Record<ParameterKey, string> = {
  temperature: "Temperature",
  maxTokens: "최대 출력 토큰",
  reasoningEffort: "추론 강도",
};
export const PARAMETER_NAMES: Record<ParameterKey, string> = {
  temperature: "temperature",
  maxTokens: "max_tokens",
  reasoningEffort: "reasoning",
};

export function parameterIssue(
  parameter: TuningParameter,
  value: number | string,
) {
  const label = PARAMETER_LABELS[parameter.key];
  if (parameter.kind === "choice")
    return parameter.options.some((option) => option.value === value)
      ? undefined
      : `지원하는 ${label} 값을 선택하시기 바랍니다.`;
  if (
    typeof value !== "number" ||
    !Number.isFinite(value) ||
    value < parameter.min ||
    value > parameter.max ||
    (parameter.key === "maxTokens" && !Number.isSafeInteger(value))
  )
    return `${label} 값은 ${parameter.min}~${parameter.max} 범위${parameter.key === "maxTokens" ? "의 정수" : "의 숫자"}로 입력하시기 바랍니다.`;
}
