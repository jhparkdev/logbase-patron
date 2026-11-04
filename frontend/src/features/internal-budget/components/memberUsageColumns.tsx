import { Badge } from "../../../shared/components/ui/Badge";
import type { Column } from "../../../shared/components/ui/DataTable";
import {
  formatCount,
  formatKstDate,
  formatKstDateTime,
  formatUsd,
} from "../../../shared/lib/format";
import type { MemberUsage } from "../api/budget";
import { memberStatusLabel } from "../lib/view";

/** 읽지 못한 구성원의 값 칸. 0이 아니라 값이 없는 것이다(이력 표의 Token 모름과 같은 표시). */
const NO_VALUE = "–";

function valueOrNone<T>(
  value: T | null | undefined,
  format: (value: T) => string,
) {
  return value == null ? NO_VALUE : format(value);
}

function MemberName({ row }: { row: MemberUsage }) {
  if (row.status === "OK") {
    return row.member_name;
  }
  // 값을 모르는 상태라 비용 미확인과 같은 노란색이다
  return (
    <span className="inline-flex items-center gap-2">
      <span>{row.member_name}</span>
      <Badge tone="yellow">{memberStatusLabel(row.status)}</Badge>
    </span>
  );
}

/** 결제 기간 기준 값이라 조회 기간과 무관하고, 시안에 없던 표라 정렬하지 않는다. */
export const MEMBER_USAGE_COLUMNS: Column<MemberUsage>[] = [
  {
    key: "member",
    header: "구성원",
    render: (row) => <MemberName row={row} />,
  },
  {
    key: "credits",
    header: "사용 크레딧 (USD)",
    align: "right",
    render: (row) =>
      valueOrNone(row.used_credits, (amount) => formatUsd(amount, "summary")),
  },
  {
    key: "requests",
    header: "요청 수",
    align: "right",
    render: (row) => valueOrNone(row.request_count, formatCount),
  },
  {
    key: "input",
    header: "입력 Token",
    align: "right",
    render: (row) => valueOrNone(row.input_tokens, formatCount),
  },
  {
    key: "output",
    header: "출력 Token",
    align: "right",
    render: (row) => valueOrNone(row.output_tokens, formatCount),
  },
  {
    key: "remaining",
    header: "남은 크레딧 (USD)",
    align: "right",
    render: (row) =>
      valueOrNone(row.remaining_credits, (amount) =>
        formatUsd(amount, "summary"),
      ),
  },
  {
    key: "period",
    header: "결제 기간",
    render: (row) =>
      row.period_start == null || row.period_end == null
        ? NO_VALUE
        : `${formatKstDate(row.period_start)} ~ ${formatKstDate(row.period_end)}`,
  },
  {
    key: "fetchedAt",
    header: "기준 시각",
    render: (row) => formatKstDateTime(row.fetched_at),
  },
];
