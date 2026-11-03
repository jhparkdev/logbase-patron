import { useSuspenseQuery } from "@tanstack/react-query";
import { CostAmount } from "../../../shared/components/ui/CostAmount";
import { DataBlock } from "../../../shared/components/ui/DataBlock";
import {
  type Column,
  DataTable,
} from "../../../shared/components/ui/DataTable";
import { ExecutionBadge } from "../../../shared/components/ui/ExecutionBadge";
import { Pagination } from "../../../shared/components/ui/Pagination";
import { RefreshingBar } from "../../../shared/components/ui/RefreshingBar";
import { Result } from "../../../shared/components/ui/Result";
import { SectionCard } from "../../../shared/components/ui/SectionCard";
import { TableSkeleton } from "../../../shared/components/ui/TableSkeleton";
import { TextLink } from "../../../shared/components/ui/TextLink";
import { formatCount, formatKstDateTime } from "../../../shared/lib/format";
import { costView, executionStatus } from "../../../shared/lib/request";
import { type CustomerRequestRow, requestRowsOptions } from "../api/usage";
import { usePageChange, useRequestSort } from "../hooks/useUsageList";
import type { CustomerUsageSearch } from "../lib/search";
import { modelName } from "../lib/view";
import { ViewAllLink } from "./ViewAllLink";

const TITLE = "상세 API 호출 내역";

/** 불러오는 동안 보여 줄 회색 행 수 */
const LOADING_ROWS = 5;
/** 고객을 알 수 없는 호출 */
const UNCLASSIFIED_LABEL = "미분류";
/** 작업 유형이나 토큰 수를 알 수 없을 때. 비용 미확인과 달리 금액이 아니다. */
const NO_VALUE = "–";

/** 실패·Timeout 호출은 행 바탕을 연하게 물들여 훑어볼 때 먼저 보이게 한다. */
const ROW_TINT_CLASS: Partial<
  Record<ReturnType<typeof executionStatus>["tone"], string>
> = {
  red: "bg-red-50/60",
  yellow: "bg-yellow-50/60",
};

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
          resetScroll={false}
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
    render: (row) => {
      const { provider, name } = modelName(row.model);
      return (
        <>
          {provider && <span className="text-grey-500">{provider}/</span>}
          <span className="font-semibold">{name}</span>
        </>
      );
    },
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
        rowClassName={(row) =>
          ROW_TINT_CLASS[executionStatus(row.status).tone] ?? ""
        }
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
