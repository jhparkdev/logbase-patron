import type { components } from "../../../shared/api/schema";
import type { CostAmountView } from "../../../shared/components/ui/CostAmount";
import { formatCount } from "../../../shared/lib/format";
import { testCostView } from "./view";

type ConnectionTestResult = components["schemas"]["ConnectionTestResult"];

export type TestStatCell =
  | { label: string; value: string; unit?: string }
  | { label: string; cost: CostAmountView };

// 아직 실행하지 않은 칸. 값을 모르는 "미확인"과는 다르다
const NOT_RUN = "—";
const UNKNOWN_LABEL = "미확인";
const MS_PER_SECOND = 1000;
const SECONDS_DIGITS = 2;
const LABELS = {
  latency: "응답 속도",
  input: "Input 토큰",
  output: "Output 토큰",
  cost: "호출 비용",
} as const;

const countOrUnknown = (count: number | null) =>
  count === null ? UNKNOWN_LABEL : formatCount(count);

/** 패널에서 이번에 실행한 연결 테스트의 숫자 네 칸. 결과가 없으면 빈 표시 */
export function testStatCells(
  result: ConnectionTestResult | undefined,
): TestStatCell[] {
  if (result === undefined) {
    return Object.values(LABELS).map((label) => ({ label, value: NOT_RUN }));
  }
  return [
    result.latency_ms === null
      ? { label: LABELS.latency, value: UNKNOWN_LABEL }
      : {
          label: LABELS.latency,
          value: (result.latency_ms / MS_PER_SECOND).toFixed(SECONDS_DIGITS),
          unit: "초",
        },
    { label: LABELS.input, value: countOrUnknown(result.input_tokens) },
    { label: LABELS.output, value: countOrUnknown(result.output_tokens) },
    { label: LABELS.cost, cost: testCostView(result) },
  ];
}
