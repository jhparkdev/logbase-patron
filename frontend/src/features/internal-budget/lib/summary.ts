import { unreflectedText } from "../../../shared/lib/format";

/** 요약 카드 이름. 불러오는 중 모양과 실제 카드가 같은 이름을 쓴다. */
export const SUMMARY_LABELS = {
  confirmed: "API 확정 비용",
  estimated: "API 추정 비용",
  subscription: "월 구독료",
  total: "총 관리 비용 (추정 포함)",
} as const;

/** 총 관리 비용 카드 아래 안내. 미확인 호출이 있으면 합계 구성 대신 넣지 못한 건수를 알린다. */
export function managedTotalCaption(unknownCount: number): string {
  return unreflectedText(unknownCount) ?? "API 비용 + 구독료";
}
