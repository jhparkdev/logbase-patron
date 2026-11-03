import type { HistoryOption } from "./presentation";

/**
 * 조회 조건 선택 상자의 항목. 주소에 선택지에 없는 값이 있으면(비활성된 모델 등)
 * 그 값을 "선택한 …" 항목으로 남겨, 사용자가 보고 지울 수 있게 한다.
 */
export function historySelectOptions(
  label: string,
  options: readonly HistoryOption[],
  value: string,
  allValue = "",
) {
  const missing =
    value !== allValue && !options.some((option) => option.key === value);
  return [
    { value: allValue, label: "전체" },
    ...(missing ? [{ value, label: `선택한 ${label}` }] : []),
    ...options.map((option) => ({ value: option.key, label: option.name })),
  ];
}
