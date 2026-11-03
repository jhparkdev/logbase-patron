import { Badge } from "../../../shared/components/ui/Badge";
import { Result } from "../../../shared/components/ui/Result";
import { TextLink } from "../../../shared/components/ui/TextLink";
import { UsageBar } from "../../../shared/components/ui/UsageBar";
import {
  budgetMonthOf,
  budgetStatusBadge,
  usageView,
} from "../../../shared/lib/budget";
import { formatUsd, unreflectedText } from "../../../shared/lib/format";
import { type ProjectBudgetRow, projectRowsOptions } from "../api/budget";
import type { ListColumn } from "../lib/list";
import type { BudgetSearch } from "../lib/search";
import { ListTable } from "./ListTable";

const TITLE = "프로젝트별 예산 현황";

const COLUMNS: ListColumn<"projects", ProjectBudgetRow>[] = [
  {
    key: "project",
    header: "프로젝트명",
    render: (row) => (
      <TextLink
        from="/internal-budget"
        to="/internal-budget"
        search={(prev) => ({ ...prev, detail: row.project_id })}
        resetScroll={false}
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
  onPageChange?: (page: number) => void;
};

/** 프로젝트별 월 예산과 사용률. 예산은 월 단위라 제목 옆에 비교하는 달을 알린다. */
export function ProjectBudgetTable({
  search,
  refreshing,
  onPageChange,
}: ProjectBudgetTableProps) {
  return (
    <ListTable
      view="projects"
      title={TITLE}
      description={`${budgetMonthOf(search)} 기준 · 프로젝트명을 누르면 상세 내역과 예산을 볼 수 있어요.`}
      errorTitle="프로젝트별 예산 현황을 불러오지 못했어요"
      query={projectRowsOptions(search)}
      columns={COLUMNS}
      rowKey={(row) => String(row.project_id)}
      empty={
        <Result
          title="등록된 프로젝트가 없어요"
          description="프로젝트가 등록되면 여기에서 예산을 정할 수 있어요."
        />
      }
      refreshing={refreshing}
      onPageChange={onPageChange}
    />
  );
}
