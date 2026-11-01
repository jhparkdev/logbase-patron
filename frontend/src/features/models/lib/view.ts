import type { components } from "../../../shared/api/schema";

type ModelStatus = components["schemas"]["ModelStatus"];
type ConnectionTestStatus = components["schemas"]["ConnectionTestStatus"];

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
