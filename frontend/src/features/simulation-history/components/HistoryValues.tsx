import { Badge } from "../../../shared/components/ui/Badge";
import {
  formatCount,
  formatKstDateTime,
  formatUsd,
} from "../../../shared/lib/format";
import type { HistoryRow } from "../lib/presentation";

const dots = {
  green: "bg-green-500",
  red: "bg-red-500",
  yellow: "bg-yellow-800",
  grey: "bg-grey-400",
};
export function HistoryTimestamp({ utc }: { utc: string }) {
  const [date, time] = formatKstDateTime(utc).split(" ");
  return (
    <time dateTime={utc} className="whitespace-nowrap tabular-nums">
      <span className="block">{date}</span>
      <span className="block text-caption text-grey-600">{time}</span>
    </time>
  );
}
export function HistoryStatus({ status }: { status: HistoryRow["status"] }) {
  return (
    <span className="inline-flex items-center gap-1.5 whitespace-nowrap rounded-full border border-grey-200 px-2 py-1 text-caption font-semibold">
      <span
        aria-hidden="true"
        className={`size-1.5 rounded-full ${dots[status.tone]}`}
      />
      {status.label}
    </span>
  );
}
export function HistoryCostStatus({ cost }: { cost: HistoryRow["cost"] }) {
  return (
    <span className="inline-flex flex-wrap gap-1">
      {cost.checking && <Badge tone="grey">확인 중</Badge>}
      {cost.estimated !== null && <Badge tone="blue">추정 포함</Badge>}
      {cost.unknownCount > 0 && <Badge tone="yellow">미확인 포함</Badge>}
      {!cost.checking && cost.estimated === null && !cost.unknownCount && (
        <Badge tone={cost.confirmed === null ? "yellow" : "green"}>
          {cost.confirmed === null ? "미확인" : "확정"}
        </Badge>
      )}
    </span>
  );
}
export function HistoryCost({ cost }: { cost: HistoryRow["cost"] }) {
  return (
    <span className="inline-flex flex-col items-end gap-1">
      {cost.confirmed !== null && (
        <span className="whitespace-nowrap tabular-nums">
          ${formatUsd(cost.confirmed, "summary")}
        </span>
      )}
      {cost.estimated !== null && (
        <span className="whitespace-nowrap tabular-nums text-blue-600">
          ≈ ${formatUsd(cost.estimated, "summary")}
        </span>
      )}
      {cost.confirmed === null && cost.estimated === null && (
        <span className="whitespace-nowrap tabular-nums">미확인</span>
      )}
      {cost.unknownCount > 0 && (
        <span className="whitespace-nowrap text-caption text-yellow-900">
          미확인 {formatCount(cost.unknownCount)}건 미반영
        </span>
      )}
    </span>
  );
}
