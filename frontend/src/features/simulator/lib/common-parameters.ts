import type { ModelChoice } from "./presentation";

// 공통값을 먼저 정하고 모델을 고를 수 있도록 카탈로그에서 확인된 선택지를 모은다.
// 선택한 각 항목의 지원 여부·허용값은 실행 전 별도로 검증한다.
export function commonEffortOptions(choices: readonly ModelChoice[]) {
  const options = new Map<string, { value: string; label: string }>();
  for (const choice of choices) {
    if (!choice.selectable) continue;
    for (const parameter of choice.tuningParameters ?? []) {
      if (parameter.kind !== "choice") continue;
      for (const option of parameter.options)
        if (!options.has(option.value)) options.set(option.value, option);
    }
  }
  return [...options.values()];
}
