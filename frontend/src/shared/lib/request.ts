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

const EXECUTION_STATUS = {
  PENDING: { label: "대기", dotClass: "bg-grey-400" },
  RUNNING: { label: "실행 중", dotClass: "bg-grey-400" },
  SUCCESS: { label: "성공", dotClass: "bg-green-500" },
  FAILED: { label: "실패", dotClass: "bg-red-500" },
  TIMEOUT: { label: "Timeout", dotClass: "bg-yellow-800" },
  CANCELLED: { label: "취소", dotClass: "bg-grey-400" },
} as const;

export function executionStatus(status: Schemas["RequestStatus"]) {
  return EXECUTION_STATUS[status];
}
