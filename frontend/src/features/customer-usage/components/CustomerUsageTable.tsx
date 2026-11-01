import { useSuspenseQuery } from "@tanstack/react-query";
import { Badge } from "../../../shared/components/ui/Badge";
import { DataBlock } from "../../../shared/components/ui/DataBlock";
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
import { UsageBar } from "../../../shared/components/ui/UsageBar";
import { budgetStatusBadge, usageView } from "../../../shared/lib/budget";
import {
  formatCount,
  formatUsd,
  isZeroAmount,
  unreflectedText,
} from "../../../shared/lib/format";
import { type CustomerUsageRow, customerRowsOptions } from "../api/usage";
import { useCustomerSort, usePageChange } from "../hooks/useUsageList";
import type { CustomerUsageSearch } from "../lib/search";
import { ViewAllLink } from "./ViewAllLink";

const TITLE = "고객별 사용 현황";

/** 불러오는 동안 보여 줄 회색 행 수 */
const LOADING_ROWS = 5;
/** 고객을 알 수 없는 호출을 모은 행 */
const UNCLASSIFIED_LABEL = "미분류";

const COLUMNS: Column<CustomerUsageRow>[] = [
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
    key: "tasks",
    header: "작업 건수",
    align: "right",
    sortable: true,
    render: (row) => formatCount(row.task_count),
  },
  {
    key: "calls",
    header: "API 호출 수",
    align: "right",
    sortable: true,
    render: (row) => formatCount(row.call_count),
  },
  {
    key: "confirmed",
    header: "확정 비용 (USD)",
    align: "right",
    sortable: true,
    render: (row) => (
      <span className="font-semibold">
        {formatUsd(row.confirmed_cost_usd, "summary")}
      </span>
    ),
  },
  {
    key: "estimated",
    header: "추정 비용 (USD)",
    align: "right",
    sortable: true,
    render: (row) =>
      `${isZeroAmount(row.estimated_cost_usd) ? "" : "≈ "}${formatUsd(row.estimated_cost_usd, "summary")}`,
  },
  {
    key: "budget",
    header: "월 예산 (USD)",
    align: "right",
    sortable: true,
    render: (row) =>
      row.budget.monthly_amount_usd === null ? (
        <span className="text-grey-600">미설정</span>
      ) : (
        formatUsd(row.budget.monthly_amount_usd, "summary")
      ),
  },
  {
    key: "usage",
    header: "사용률 (추정 포함)",
    sortable: true,
    render: (row) => <UsageCell row={row} />,
  },
  {
    key: "status",
    header: "상태",
    sortable: true,
    render: (row) => {
      const badge = budgetStatusBadge(row.budget.status);
      return <Badge tone={badge.tone}>{badge.label}</Badge>;
    },
  },
];

function UsageCell({ row }: { row: CustomerUsageRow }) {
  const unreflected = unreflectedText(row.budget.unknown_cost_count);
  return (
    <div className="flex w-44 flex-col gap-0.5">
      <UsageBar usage={usageView(row.budget)} />
      {unreflected && (
        <span className="text-caption text-grey-600">{unreflected}</span>
      )}
    </div>
  );
}

type CustomerUsageTableProps = {
  search: CustomerUsageSearch;
  refreshing: boolean;
  budgetMonth: string;
  /** 전체보기에서는 전체보기 링크를 두지 않고 페이지 이동을 둔다. */
  fullView?: boolean;
};

/** 고객·서비스별 사용량과 고객 예산 사용률. 예산은 월 단위라 제목 옆에 비교하는 달을 알린다. */
export function CustomerUsageTable({
  search,
  refreshing,
  budgetMonth,
  fullView = false,
}: CustomerUsageTableProps) {
  return (
    <SectionCard
      title={TITLE}
      description={`${budgetMonth} 기준`}
      action={
        fullView ? undefined : <ViewAllLink view="customers" title={TITLE} />
      }
    >
      {refreshing && <RefreshingBar />}
      <DataBlock
        fallback={<TableSkeleton rows={LOADING_ROWS} />}
        errorTitle="고객별 사용 현황을 불러오지 못했어요"
        resetKey={JSON.stringify(customerRowsOptions(search).queryKey)}
      >
        <CustomerRows search={search} fullView={fullView} />
      </DataBlock>
    </SectionCard>
  );
}

function CustomerRows({
  search,
  fullView,
}: {
  search: CustomerUsageSearch;
  fullView: boolean;
}) {
  const { data } = useSuspenseQuery(customerRowsOptions(search));
  const { sort, onSortChange } = useCustomerSort();
  const onPageChange = usePageChange();
  return (
    <>
      <DataTable
        caption={TITLE}
        columns={COLUMNS}
        rows={data.items}
        rowKey={(row) => `${row.customer_id ?? "none"}-${row.service_id}`}
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
