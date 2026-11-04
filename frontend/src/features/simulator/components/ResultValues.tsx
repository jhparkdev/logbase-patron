import { Badge } from "../../../shared/components/ui/Badge";
import { formatUsd } from "../../../shared/lib/format";
import type { CostView, StatusView } from "../lib/presentation";

const dot = {
  green: "bg-green-500",
  red: "bg-red-500",
  yellow: "bg-yellow-800",
  grey: "bg-grey-400",
};
export function ExecutionStatus({ status }: { status: StatusView }) {
  return (
    <span className="inline-flex items-center gap-1.5 whitespace-nowrap rounded-full border border-grey-200 px-2 py-1 text-caption font-semibold">
      <span
        aria-hidden="true"
        className={`size-1.5 rounded-full ${dot[status.tone]}`}
      />
      {status.label}
    </span>
  );
}
export function CostValue({ cost }: { cost: CostView }) {
  if (cost.kind === "unknown") return <Badge tone="yellow">미확인</Badge>;
  return (
    <span
      className={`inline-flex flex-wrap items-center justify-end gap-1 tabular-nums ${cost.kind === "estimated" ? "text-blue-600" : ""}`}
    >
      {cost.kind === "estimated" ? "≈ " : ""}$
      {formatUsd(cost.amount, "perCall")}
      {cost.kind === "estimated" && <Badge tone="blue">추정</Badge>}
    </span>
  );
}
export function durationLabel(milliseconds: number | null) {
  return milliseconds === null
    ? "미집계"
    : `${(milliseconds / 1000).toLocaleString("ko-KR", { minimumFractionDigits: 1, maximumFractionDigits: 3 })}초`;
}
