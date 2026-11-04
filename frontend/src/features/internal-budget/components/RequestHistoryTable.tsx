import { Badge } from "../../../shared/components/ui/Badge";
import { CostAmount } from "../../../shared/components/ui/CostAmount";
import { ExecutionBadge } from "../../../shared/components/ui/ExecutionBadge";
import { Result } from "../../../shared/components/ui/Result";
import { TextLink } from "../../../shared/components/ui/TextLink";
import { formatCount, formatKstDateTime } from "../../../shared/lib/format";
import { costView } from "../../../shared/lib/request";
import { type InternalRequestRow, requestRowsOptions } from "../api/budget";
import type { ListColumn } from "../lib/list";
import type { BudgetSearch } from "../lib/search";
import { originLabel } from "../lib/view";
import { ListTable } from "./ListTable";

const TITLE = "상세 API 사용 이력";

/** 프로젝트를 알 수 없는 호출 */
const UNCLASSIFIED_LABEL = "미분류";
/** 토큰 수를 알 수 없을 때. 비용 미확인과 달리 금액이 아니다. */
const NO_VALUE = "–";

const COLUMNS: ListColumn<"requests", InternalRequestRow>[] = [
  {
    key: "requestedAt",
    header: "일시",
    render: (row) => formatKstDateTime(row.requested_at),
  },
  {
    key: "project",
    header: "프로젝트",
    render: (row) =>
      row.project_id === null ? (
        UNCLASSIFIED_LABEL
      ) : (
        <TextLink
          from="/internal-budget"
          to="/internal-budget"
          search={(prev) => ({ ...prev, detail: row.project_id ?? undefined })}
          resetScroll={false}
        >
          {row.project_name}
        </TextLink>
      ),
  },
  {
    key: "model",
    header: "모델",
    render: (row) => row.model,
  },
  {
    key: "tokens",
    header: "사용량 (Token)",
    align: "right",
    render: (row) => (row.tokens === null ? NO_VALUE : formatCount(row.tokens)),
  },
  {
    key: "cost",
    header: "비용 (USD)",
    align: "right",
    render: (row) => <CostAmount cost={costView(row)} precision="perCall" />,
  },
  {
    key: "origin",
    header: "구분",
    render: (row) => <Badge tone="grey">{originLabel(row.usage_origin)}</Badge>,
  },
  {
    key: "status",
    header: "실행 상태",
    render: (row) => <ExecutionBadge status={row.status} />,
  },
];

type RequestHistoryTableProps = {
  search: BudgetSearch;
  refreshing: boolean;
  onPageChange?: (page: number) => void;
};

/**
 * 조회 조건에 맞는 내부 호출 이력. 고객 사용은 넣지 않고, 구분 칸에 호출 출처를 보여 준다.
 * 요약 화면에서는 최근 20건(그 20건 안에서 정렬), 전체보기에서는 조건에 맞는 전체다.
 */
export function RequestHistoryTable({
  search,
  refreshing,
  onPageChange,
}: RequestHistoryTableProps) {
  return (
    <ListTable
      view="requests"
      title={TITLE}
      description={onPageChange ? undefined : "최근 20건"}
      errorTitle="상세 API 사용 이력을 불러오지 못했어요"
      query={requestRowsOptions(search)}
      columns={COLUMNS}
      rowKey={(row) => row.request_id}
      empty={
        <Result
          title="이 조건에는 API 사용 내역이 없어요"
          description="기간을 넓히거나 프로젝트·모델 조건을 바꿔 보세요."
        />
      }
      refreshing={refreshing}
      onPageChange={onPageChange}
    />
  );
}
