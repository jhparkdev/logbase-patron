import type { components } from "../../../shared/api/schema";

const ORIGIN_LABEL = {
  INTERNAL_DEVELOPMENT: "내부 개발",
  SIMULATION: "시뮬레이션",
  SYSTEM_TEST: "연결 테스트",
  CUSTOMER_SERVICE: "고객 사용",
} as const;

/** 호출 출처를 화면 글자로 바꾼다. 내부 이력에는 고객 사용이 오지 않지만 값 목록이 같은 enum이라 함께 둔다. */
export function originLabel(origin: components["schemas"]["UsageOrigin"]) {
  return ORIGIN_LABEL[origin];
}

const SUBSCRIPTION_STATUS_BADGE = {
  ACTIVE: { label: "사용 중", tone: "green" },
  CANCELLED: { label: "해지", tone: "grey" },
} as const;

/** 구독료 상태를 배지 글자와 색으로 바꾼다. */
export function subscriptionStatusBadge(
  status: components["schemas"]["SubscriptionStatus"],
) {
  return SUBSCRIPTION_STATUS_BADGE[status];
}

const MEMBER_STATUS_LABEL = {
  KEY_MISSING: "Key 없음",
  KEY_EXPIRED: "Key 만료",
  KEY_INVALID: "Key 오류",
  FETCH_FAILED: "조회 실패",
} as const;

/** 사용량을 읽지 못한 구성원의 이유 배지 글자. */
export function memberStatusLabel(
  status: Exclude<components["schemas"]["CommandCodeStatus"], "OK">,
) {
  return MEMBER_STATUS_LABEL[status];
}
