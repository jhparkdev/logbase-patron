import { formatUsd, type UsdPrecision } from "../../lib/format";
import { Badge } from "./Badge";

/** 화면에 보여 줄 비용. 미확인은 금액이 없다(0으로 바꾸지 않는다). */
export type CostAmountView =
  | { kind: "confirmed" | "estimated"; amount: string }
  | { kind: "unknown"; amount: null };

type CostAmountProps = {
  cost: CostAmountView;
  precision: UsdPrecision;
};

/** 확정은 숫자, 추정은 ≈ 숫자와 추정 배지, 미확인은 미확인 배지. 단위(USD)는 표 머리글에 둔다. */
export function CostAmount({ cost, precision }: CostAmountProps) {
  if (cost.kind === "unknown") {
    return <Badge tone="yellow">미확인</Badge>;
  }
  if (cost.kind === "confirmed") {
    return <span>{formatUsd(cost.amount, precision)}</span>;
  }
  return (
    <span className="inline-flex items-center gap-1.5">
      ≈ {formatUsd(cost.amount, precision)}
      <Badge tone="blue">추정</Badge>
    </span>
  );
}
