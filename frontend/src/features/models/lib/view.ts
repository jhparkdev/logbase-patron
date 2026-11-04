import type { components } from "../../../shared/api/schema";
import type { CostAmountView } from "../../../shared/components/ui/CostAmount";
import { formatKstDateTime } from "../../../shared/lib/format";

type ModelStatus = components["schemas"]["ModelStatus"];
type ConnectionTestStatus = components["schemas"]["ConnectionTestStatus"];
type ProviderRead = components["schemas"]["ProviderRead"];
type ConnectionTestResult = components["schemas"]["ConnectionTestResult"];

/** "YYYY-MM-DD"의 글자 수 */
const DATE_LENGTH = 10;

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

/** 입력 형식 → 출력 형식 한 줄 */
export function modalitiesFlow(input: string[], output: string[]): string {
  const join = (modalities: string[]) =>
    modalities.map(modalityLabel).join("·");
  return `${join(input)} → ${join(output)}`;
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

/** 테스트 비용 표시. 금액이 없으면 상태와 관계없이 미확인(0으로 바꾸지 않음) */
export function testCostView({
  cost_usd,
  cost_status,
}: Pick<ConnectionTestResult, "cost_usd" | "cost_status">): CostAmountView {
  if (cost_usd === null || cost_status === "UNKNOWN") {
    return { kind: "unknown", amount: null };
  }
  return {
    kind: cost_status === "ESTIMATED" ? "estimated" : "confirmed",
    amount: cost_usd,
  };
}

// TESTING으로 돌아가는 상태 변경은 없음. 가능 여부(최근 성공 테스트 유무 등)는 서버가 판단
export type ChangeableStatus = Exclude<ModelStatus, "TESTING">;

// 서버 문구 대신 쓰는 거절 안내. 서버가 검사하는 시간 조건을 화면 문구에 적지 않기로 한 결정(P-03)
const STATUS_CHANGE_ERROR_MESSAGES: Partial<Record<string, string>> = {
  TEST_NOT_PASSED:
    "성공한 연결 테스트가 있어야 사용 시작할 수 있어요. 연결 테스트를 먼저 실행해 주세요.",
};

/** 상태 변경 거절 문구. 우리 문구가 있는 코드만 바꾸고, 나머지는 서버 문구 그대로 */
export function statusChangeErrorMessage(
  code: string | undefined,
  serverMessage: string,
): string {
  return (code && STATUS_CHANGE_ERROR_MESSAGES[code]) || serverMessage;
}

/** 상태 전환 칸 세 개. 검증 중으로는 돌아갈 수 없고 현재 상태는 다시 고를 수 없다 */
export function statusSegments(current: ModelStatus) {
  return MODEL_STATUSES.map((status) => ({
    status,
    ...STATUS_BADGES[status],
    selected: status === current,
    disabled: status === "TESTING" || status === current,
  }));
}

/** 상태 칸 아래 안내. 누를 수 있는 칸마다 누르면 무슨 일이 생기는지 */
export function statusNotices(current: ModelStatus) {
  return statusSegments(current)
    .filter((segment) => !segment.disabled && segment.status !== "TESTING")
    .map((segment) => ({
      label: segment.label,
      hint: STATUS_CHANGES[segment.status as ChangeableStatus].hint,
    }));
}

const STATUS_CHANGES = {
  ACTIVE: {
    action: "사용 시작",
    hint: "시뮬레이터에서 이 모델을 선택할 수 있게 돼요.",
  },
  INACTIVE: {
    action: "사용 중단",
    hint: "새 시뮬레이션에서 이 모델이 빠져요. 지난 사용 기록과 결과는 그대로 남아요.",
  },
} as const satisfies Record<ChangeableStatus, { action: string; hint: string }>;

/** 버튼 글자(동사)와 확인창 안내 */
export function statusChangeText(target: ChangeableStatus) {
  return STATUS_CHANGES[target];
}

const NONE_LABEL = "없음";

/** 시각이 없으면 빈칸 대신 없음, 있으면 KST */
export function timeOrNone(utc: string | null): string {
  return utc === null ? NONE_LABEL : formatKstDateTime(utc);
}

/** OpenRouter에 올라온 날. 모르면 null(보여 주지 않음) */
export function releasedLabel(createdAt: string | null): string | null {
  return createdAt === null
    ? null
    : `${formatKstDateTime(createdAt).slice(0, DATE_LENGTH)} 출시`;
}
