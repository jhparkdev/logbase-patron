import { useSuspenseQuery } from "@tanstack/react-query";
import { Badge } from "../../../shared/components/ui/Badge";
import { CostAmount } from "../../../shared/components/ui/CostAmount";
import { DataBlock } from "../../../shared/components/ui/DataBlock";
import {
  type Column,
  DataTable,
} from "../../../shared/components/ui/DataTable";
import { ExecutionBadge } from "../../../shared/components/ui/ExecutionBadge";
import { Pagination } from "../../../shared/components/ui/Pagination";
import { RefreshingBar } from "../../../shared/components/ui/RefreshingBar";
import { SectionCard } from "../../../shared/components/ui/SectionCard";
import { TableSkeleton } from "../../../shared/components/ui/TableSkeleton";
import { TextLink } from "../../../shared/components/ui/TextLink";
import { formatCount, formatKstDateTime } from "../../../shared/lib/format";
import { costView } from "../../../shared/lib/request";
import { type InternalRequestRow, requestRowsOptions } from "../api/budget";
import { useListSort } from "../hooks/useListSort";
import type { BUDGET_LIST_SORTS, BudgetSearch } from "../lib/search";
import { originLabel } from "../lib/view";
import { NoUsageResult } from "./NoUsageResult";
import { ViewAllLink } from "./ViewAllLink";

const TITLE = "상세 API 사용 이력";

/** 불러오는 동안 보여 줄 회색 행 수 */
const LOADING_ROWS = 5;
/** 프로젝트를 알 수 없는 호출 */
const UNCLASSIFIED_LABEL = "미분류";
/** 토큰 수를 알 수 없을 때. 비용 미확인과 달리 금액이 아니다. */
const NO_VALUE = "–";

/** 칸의 key는 정렬 허용 목록의 값만 쓴다. 머리글을 누르면 그 값이 주소와 요청의 정렬 칸이 된다. */
type RequestColumn = Omit<Column<InternalRequestRow>, "key" | "sortable"> & {
  key: (typeof BUDGET_LIST_SORTS)["requests"][number];
  sortable: true;
};

const COLUMNS: RequestColumn[] = [
  {
    key: "requestedAt",
    header: "일시",
    sortable: true,
    render: (row) => formatKstDateTime(row.requested_at),
  },
  {
    key: "project",
    header: "프로젝트",
    sortable: true,
    render: (row) =>
      row.project_id === null ? (
        UNCLASSIFIED_LABEL
      ) : (
        <TextLink
          from="/internal-budget"
          to="/internal-budget"
          search={(prev) => ({ ...prev, project: row.project_id ?? undefined })}
        >
          {row.project_name}
        </TextLink>
      ),
  },
  {
    key: "model",
    header: "모델",
    sortable: true,
    render: (row) => row.model,
  },
  {
    key: "tokens",
    header: "사용량 (Token)",
    align: "right",
    sortable: true,
    render: (row) => (row.tokens === null ? NO_VALUE : formatCount(row.tokens)),
  },
  {
    key: "cost",
    header: "비용 (USD)",
    align: "right",
    sortable: true,
    render: (row) => <CostAmount cost={costView(row)} precision="perCall" />,
  },
  {
    key: "origin",
    header: "구분",
    sortable: true,
    render: (row) => <Badge tone="grey">{originLabel(row.usage_origin)}</Badge>,
  },
  {
    key: "status",
    header: "실행 상태",
    sortable: true,
    render: (row) => <ExecutionBadge status={row.status} />,
  },
];

type RequestHistoryTableProps = {
  search: BudgetSearch;
  refreshing: boolean;
  /** 있으면 전체보기라 아래에 페이지 이동을 두고, 없으면 요약 화면의 표다. */
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
    <SectionCard
      title={TITLE}
      description={onPageChange ? undefined : "최근 20건"}
      action={
        onPageChange ? undefined : <ViewAllLink view="requests" title={TITLE} />
      }
    >
      {refreshing && <RefreshingBar />}
      <DataBlock
        fallback={<TableSkeleton rows={LOADING_ROWS} />}
        errorTitle="상세 API 사용 이력을 불러오지 못했어요"
        resetKey={JSON.stringify(requestRowsOptions(search).queryKey)}
      >
        <RequestRows search={search} onPageChange={onPageChange} />
      </DataBlock>
    </SectionCard>
  );
}

function RequestRows({
  search,
  onPageChange,
}: Pick<RequestHistoryTableProps, "search" | "onPageChange">) {
  const { data } = useSuspenseQuery(requestRowsOptions(search));
  const { sort, onSortChange } = useListSort("requests");
  return (
    <>
      <DataTable
        caption={TITLE}
        columns={COLUMNS}
        rows={data.items}
        rowKey={(row) => row.request_id}
        sort={sort}
        onSortChange={onSortChange}
        empty={<NoUsageResult />}
      />
      {onPageChange && (
        <Pagination
          total={data.total}
          pageSize={data.page_size}
          page={data.page}
          onPageChange={onPageChange}
        />
      )}
    </>
  );
}
