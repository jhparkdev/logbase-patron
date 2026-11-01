import type { components } from "../../../shared/api/schema";

type ModelStatus = components["schemas"]["ModelStatus"];
type ConnectionTestStatus = components["schemas"]["ConnectionTestStatus"];
type ProviderRead = components["schemas"]["ProviderRead"];

const STATUS_BADGES = {
  TESTING: { tone: "blue", label: "검증 중" },
  ACTIVE: { tone: "green", label: "사용 중" },
  INACTIVE: { tone: "grey", label: "사용 중단" },
} as const satisfies Record<ModelStatus, { tone: string; label: string }>;

export function statusBadge(status: ModelStatus) {
  return STATUS_BADGES[status];
}

const TEST_RESULTS = {
  SUCCESS: { label: "성공", dot: "green" },
  FAILED: { label: "실패", dot: "red" },
  TIMEOUT: { label: "시간 초과", dot: "red" },
} as const satisfies Record<
  ConnectionTestStatus,
  { label: string; dot: string }
>;

export function testResultView(status: ConnectionTestStatus) {
  return TEST_RESULTS[status];
}

const MODALITY_LABELS: Record<string, string> = {
  text: "텍스트",
  image: "이미지",
  file: "파일",
  audio: "오디오",
  video: "비디오",
};

/** 새 입력 형식이 추가돼도 화면이 비지 않게 모르는 형식은 원문 표시 */
export function modalityLabel(modality: string): string {
  return MODALITY_LABELS[modality] ?? modality;
}

export function modalitiesLabel(modalities: string[]): string {
  return modalities.map(modalityLabel).join(", ");
}

// 선택지 순서. 상태가 늘면 STATUS_BADGES에서 타입 오류가 나므로 여기도 함께 고친다.
export const MODEL_STATUSES = [
  "TESTING",
  "ACTIVE",
  "INACTIVE",
] as const satisfies readonly ModelStatus[];

export const STATUS_OPTIONS = [
  { value: "", label: "상태 전체" },
  ...MODEL_STATUSES.map((status) => ({
    value: status,
    label: STATUS_BADGES[status].label,
  })),
];

/** 선택 상자의 값(전체는 빈 문자열)을 상태로 변환. 전체는 undefined */
export function statusOfOption(value: string): ModelStatus | undefined {
  return MODEL_STATUSES.find((status) => status === value);
}

/** 제공사 선택지(모델 수 포함). 고른 제공사가 목록에 없어도(로딩·조회 실패) 이름만 남겨 선택이 풀리지 않게 함 */
export function providerOptions(
  providers: ProviderRead[],
  selected: string | undefined,
) {
  const options = providers.map((item) => ({
    value: item.provider,
    label: `${item.provider} (${item.model_count})`,
  }));
  if (selected !== undefined && !options.some((o) => o.value === selected)) {
    options.push({ value: selected, label: selected });
  }
  return [{ value: "", label: "Provider 전체" }, ...options];
}
