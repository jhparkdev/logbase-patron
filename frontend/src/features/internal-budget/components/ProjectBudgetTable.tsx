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
import {
  budgetMonthOf,
  budgetStatusBadge,
  usageView,
} from "../../../shared/lib/budget";
import { formatUsd, unreflectedText } from "../../../shared/lib/format";
import { type ProjectBudgetRow, projectRowsOptions } from "../api/budget";
import { useListSort } from "../hooks/useListSort";
import type { ListColumn } from "../lib/list";
import type { BudgetSearch } from "../lib/search";
import { ViewAllLink } from "./ViewAllLink";

const TITLE = "프로젝트별 예산 현황";

/** 불러오는 동안 보여 줄 회색 행 수 */
const LOADING_ROWS = 5;

// 칸 key는 정렬 허용 목록에 있는 값만 쓸 수 있다(ListColumn). 모든 칸을 정렬할 수 있다.
const COLUMNS: (ListColumn<"projects"> &
  Pick<Column<ProjectBudgetRow>, "render">)[] = [
  {
    key: "project",
    header: "프로젝트명",
    render: (row) => (
      <TextLink
        from="/internal-budget"
        to="/internal-budget"
        search={(prev) => ({ ...prev, project: row.project_id })}
      >
        {row.project_name}
      </TextLink>
    ),
  },
  {
    key: "budget",
    header: "월 예산 (USD)",
    align: "right",
    render: (row) =>
      row.monthly_amount_usd === null ? (
        <span className="text-grey-600">미설정</span>
      ) : (
        formatUsd(row.monthly_amount_usd, "summary")
      ),
  },
  {
    key: "used",
    header: "사용액 (USD, 추정 포함)",
    align: "right",
    render: (row) => formatUsd(row.used_usd, "summary"),
  },
  {
    key: "usage",
    header: "사용률",
    render: (row) => <UsageCell row={row} />,
  },
  {
    key: "status",
    header: "상태",
    render: (row) => {
      const badge = budgetStatusBadge(row.status);
      return <Badge tone={badge.tone}>{badge.label}</Badge>;
    },
  },
];

function UsageCell({ row }: { row: ProjectBudgetRow }) {
  const unreflected = unreflectedText(row.unknown_cost_count);
  return (
    <div className="flex w-44 flex-col gap-0.5">
      <UsageBar usage={usageView(row)} />
      {unreflected && (
        <span className="text-caption text-grey-600">{unreflected}</span>
      )}
    </div>
  );
}

type ProjectBudgetTableProps = {
  search: BudgetSearch;
  refreshing: boolean;
  /** 있으면 전체보기라 아래에 페이지 이동을 두고, 없으면 요약 화면의 표다. */
  onPageChange?: (page: number) => void;
};

/** 프로젝트별 월 예산과 사용률. 예산은 월 단위라 제목 옆에 비교하는 달을 알린다. */
export function ProjectBudgetTable({
  search,
  refreshing,
  onPageChange,
}: ProjectBudgetTableProps) {
  return (
    <SectionCard
      title={TITLE}
      description={`${budgetMonthOf(search)} 기준 · 프로젝트명을 누르면 상세 내역과 예산을 볼 수 있어요.`}
      action={
        onPageChange ? undefined : <ViewAllLink view="projects" title={TITLE} />
      }
    >
      {refreshing && <RefreshingBar />}
      <DataBlock
        fallback={<TableSkeleton rows={LOADING_ROWS} />}
        errorTitle="프로젝트별 예산 현황을 불러오지 못했어요"
        resetKey={JSON.stringify(projectRowsOptions(search).queryKey)}
      >
        <ProjectRows search={search} onPageChange={onPageChange} />
      </DataBlock>
    </SectionCard>
  );
}

function ProjectRows({
  search,
  onPageChange,
}: Pick<ProjectBudgetTableProps, "search" | "onPageChange">) {
  const { data } = useSuspenseQuery(projectRowsOptions(search));
  const { sort, onSortChange } = useListSort("projects");
  return (
    <>
      <DataTable
        caption={TITLE}
        columns={COLUMNS.map((column) => ({ ...column, sortable: true }))}
        rows={data.items}
        rowKey={(row) => String(row.project_id)}
        sort={sort}
        onSortChange={onSortChange}
        empty={
          <Result
            title="등록된 프로젝트가 없어요"
            description="프로젝트가 등록되면 여기에서 예산을 정할 수 있어요."
          />
        }
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
