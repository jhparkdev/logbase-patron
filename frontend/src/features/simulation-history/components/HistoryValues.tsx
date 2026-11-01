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
const COST_STATUS_TONES = {
  "확인 중": "grey",
  "미확인 포함": "yellow",
  "추정 포함": "blue",
  확정: "green",
} as const satisfies Record<HistoryRow["cost"]["checkStatus"], string>;
export function HistoryCostStatus({ cost }: { cost: HistoryRow["cost"] }) {
  return (
    <span className="inline-flex flex-wrap gap-1">
      <Badge tone={COST_STATUS_TONES[cost.checkStatus]}>
        {cost.checkStatus}
      </Badge>
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
      {/* 비용 상태가 미확인 포함이면 배지에 드러나지 않으므로 금액 쪽에 남긴다 */}
      {cost.estimated !== null && cost.checkStatus !== "추정 포함" && (
        <span className="whitespace-nowrap text-caption text-blue-600">
          추정 포함
        </span>
      )}
      {cost.unknownCount > 0 && (
        <span className="whitespace-nowrap text-caption text-yellow-900">
          미확인 {formatCount(cost.unknownCount)}건 미반영
        </span>
      )}
    </span>
  );
}
