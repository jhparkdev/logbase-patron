import { useSuspenseQuery } from "@tanstack/react-query";
import { CostAmount } from "../../../shared/components/ui/CostAmount";
import {
  type Column,
  DataTable,
} from "../../../shared/components/ui/DataTable";
import { Pagination } from "../../../shared/components/ui/Pagination";
import { RefreshingBar } from "../../../shared/components/ui/RefreshingBar";
import { Result } from "../../../shared/components/ui/Result";
import { SectionCard } from "../../../shared/components/ui/SectionCard";
import { TableSkeleton } from "../../../shared/components/ui/TableSkeleton";
import { TextLink } from "../../../shared/components/ui/TextLink";
import { formatCount, formatKstDateTime } from "../../../shared/lib/format";
import { type CustomerRequestRow, requestRowsOptions } from "../api/usage";
import { usePageChange, useRequestSort } from "../hooks/useUsageList";
import type { CustomerUsageSearch } from "../lib/search";
import { costView, executionStatus } from "../lib/view";
import { DataBlock } from "./DataBlock";
import { ViewAllLink } from "./ViewAllLink";

const TITLE = "상세 API 호출 내역";

/** 불러오는 동안 보여 줄 회색 행 수 */
const LOADING_ROWS = 5;
/** 고객을 알 수 없는 호출 */
const UNCLASSIFIED_LABEL = "미분류";
/** 작업 유형이나 토큰 수를 알 수 없을 때. 비용 미확인과 달리 금액이 아니다. */
const NO_VALUE = "–";

const COLUMNS: Column<CustomerRequestRow>[] = [
  {
    key: "requestedAt",
    header: "호출 시각",
    sortable: true,
    render: (row) => formatKstDateTime(row.requested_at),
  },
  {
    key: "customer",
    header: "고객",
    sortable: true,
    render: (row) =>
      row.customer_id === null ? (
        UNCLASSIFIED_LABEL
      ) : (
        <TextLink
          from="/customer-usage"
          to="/customer-usage"
          search={(prev) => ({ ...prev, detail: row.customer_id ?? undefined })}
        >
          {row.customer_name}
        </TextLink>
      ),
  },
  {
    key: "service",
    header: "서비스",
    sortable: true,
    render: (row) => row.service_name,
  },
  {
    key: "model",
    header: "모델",
    sortable: true,
    render: (row) => row.model,
  },
  {
    key: "taskType",
    header: "작업 유형",
    sortable: true,
    render: (row) => row.task_type_label ?? NO_VALUE,
  },
  {
    key: "tokens",
    header: "토큰 수",
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
    key: "status",
    header: "실행 상태",
    sortable: true,
    render: (row) => <ExecutionBadge status={row.status} />,
  },
];

/** 비용 상태 배지와 모양을 구분하려고 테두리와 점으로 그린다(docs/design/tokens.md). */
function ExecutionBadge({ status }: { status: CustomerRequestRow["status"] }) {
  const { label, dotClass } = executionStatus(status);
  return (
    <span className="inline-flex h-6 items-center gap-1.5 rounded-full border border-grey-200 px-2 text-caption font-bold whitespace-nowrap">
      <span
        aria-hidden="true"
        className={`size-1.5 rounded-full ${dotClass}`}
      />
      {label}
    </span>
  );
}

type RequestTableProps = {
  search: CustomerUsageSearch;
  refreshing: boolean;
  fullView?: boolean;
};

/**
 * 조회 조건에 맞는 AI 호출. 실패·Timeout도 넣는다.
 * 요약 화면에서는 최근 20건, 전체보기에서는 조건에 맞는 전체다.
 */
export function RequestTable({
  search,
  refreshing,
  fullView = false,
}: RequestTableProps) {
  return (
    <SectionCard
      title={TITLE}
      description={fullView ? undefined : "최근 20건"}
      action={
        fullView ? undefined : <ViewAllLink view="requests" title={TITLE} />
      }
    >
      {refreshing && <RefreshingBar />}
      <DataBlock
        fallback={<TableSkeleton rows={LOADING_ROWS} />}
        errorTitle="호출 내역을 불러오지 못했어요"
        resetKey={JSON.stringify(requestRowsOptions(search).queryKey)}
      >
        <RequestRows search={search} fullView={fullView} />
      </DataBlock>
    </SectionCard>
  );
}

function RequestRows({
  search,
  fullView,
}: {
  search: CustomerUsageSearch;
  fullView: boolean;
}) {
  const { data } = useSuspenseQuery(requestRowsOptions(search));
  const { sort, onSortChange } = useRequestSort();
  const onPageChange = usePageChange();
  return (
    <>
      <DataTable
        caption={TITLE}
        columns={COLUMNS}
        rows={data.items}
        rowKey={(row) => row.request_id}
        sort={sort}
        onSortChange={onSortChange}
        empty={
          <Result
            title="이 조건에는 API 호출 내역이 없어요"
            description="조회 조건을 바꿔 보세요."
          />
        }
      />
      {fullView && (
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
