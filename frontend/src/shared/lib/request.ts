import type { components } from "../api/schema";
import type { CostAmountView } from "../components/ui/CostAmount";

type Schemas = components["schemas"];

/** 호출 1건의 비용을 표시용으로 바꾼다. 미확인은 금액이 없다. */
export function costView(row: {
  cost_status: Schemas["CostStatus"];
  cost_usd: string | null;
}): CostAmountView {
  if (row.cost_status === "UNKNOWN" || row.cost_usd === null) {
    return { kind: "unknown", amount: null };
  }
  return {
    kind: row.cost_status === "CONFIRMED" ? "confirmed" : "estimated",
    amount: row.cost_usd,
  };
}

/** tone은 색의 뜻이다. 아이콘과 실제 색은 화면이 정한다. */
const EXECUTION_STATUS = {
  PENDING: { label: "대기", tone: "grey" },
  RUNNING: { label: "실행 중", tone: "grey" },
  SUCCESS: { label: "성공", tone: "green" },
  FAILED: { label: "실패", tone: "red" },
  TIMEOUT: { label: "Timeout", tone: "yellow" },
  CANCELLED: { label: "취소", tone: "grey" },
} as const;

export function executionStatus(status: Schemas["RequestStatus"]) {
  return EXECUTION_STATUS[status];
}
