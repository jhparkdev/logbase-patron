import { Result } from "../../../shared/components/ui/Result";
import { SectionCard } from "../../../shared/components/ui/SectionCard";
import { useListSort } from "../hooks/useListSort";
import type { ListColumn, PagingControls } from "../lib/list";
import { PendingTable } from "./PendingTable";
import { ViewAllLink } from "./ViewAllLink";

const TITLE = "프로젝트별 예산 현황";

const COLUMNS: ListColumn<"projects">[] = [
  { key: "project", header: "프로젝트명" },
  { key: "budget", header: "월 예산 (USD)", align: "right" },
  { key: "used", header: "사용액 (USD, 추정 포함)", align: "right" },
  { key: "usage", header: "사용률" },
  { key: "status", header: "상태" },
];

type ProjectBudgetTableProps = {
  /** 예산을 비교하는 달 "YYYY-MM" */
  month: string;
  /** 있으면 전체보기, 없으면 요약 화면의 표 */
  paging?: PagingControls;
};

/** 프로젝트별 월 예산과 사용률. */
export function ProjectBudgetTable({ month, paging }: ProjectBudgetTableProps) {
  const sorting = useListSort("projects");
  return (
    <SectionCard
      title={TITLE}
      description={`${month} 기준 · 프로젝트명을 누르면 상세 내역과 예산을 볼 수 있어요.`}
      action={
        paging ? undefined : <ViewAllLink view="projects" title={TITLE} />
      }
    >
      <PendingTable
        caption={TITLE}
        columns={COLUMNS}
        empty={
          <Result
            title="등록된 프로젝트가 없어요"
            description="프로젝트가 등록되면 여기에서 예산을 정할 수 있어요."
          />
        }
        sorting={sorting}
        paging={paging}
      />
    </SectionCard>
  );
}
