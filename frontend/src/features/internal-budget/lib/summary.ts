import { unreflectedText } from "../../../shared/lib/format";

/** 요약 카드 이름. 불러오는 중 모양과 실제 카드가 같은 이름을 쓴다. */
export const SUMMARY_LABELS = {
  confirmed: "API 확정 비용",
  estimated: "API 추정 비용",
  subscription: "월 구독료",
  total: "총 관리 비용 (추정 포함)",
} as const;

/** 월 구독료 카드 아래 안내. 모델 조건에서는 서버가 구독료를 빼므로 그 사실을 알린다. */
export function subscriptionCaption(subscriptionExcluded: boolean): string {
  return subscriptionExcluded
    ? "모델 조건에서는 구독료를 빼고 보여요"
    : "각 서비스 월 구독료";
}

/** 총 관리 비용 카드 아래 안내. 미확인 호출이 있으면 합계 구성 대신 넣지 못한 건수를 알린다. */
export function managedTotalCaption(
  unknownCount: number,
  subscriptionExcluded: boolean,
): string {
  return (
    unreflectedText(unknownCount) ??
    (subscriptionExcluded ? "API 비용만 (구독료 제외)" : "API 비용 + 구독료")
  );
}
