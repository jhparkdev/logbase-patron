import { createFileRoute } from "@tanstack/react-router";
import { BudgetFilters } from "../../features/internal-budget/components/BudgetFilters";
import { parseBudgetSearch } from "../../features/internal-budget/lib/search";
import { PageHeader } from "../../shared/components/ui/PageHeader";

export const Route = createFileRoute("/_app/internal-budget")({
  // 주소를 읽을 때마다 현재 시각으로 기본 기간(이번 달)을 정한다.
  validateSearch: (search) => parseBudgetSearch(search, new Date()),
  component: InternalBudgetPage,
});

function InternalBudgetPage() {
  const search = Route.useSearch();
  const navigate = Route.useNavigate();

  return (
    <>
      <PageHeader
        title="내부 AI 예산 관리"
        description="사내 프로젝트의 API 비용과 구독료를 함께 관리할 수 있어요."
      />
      <BudgetFilters
        // 뒤로 가기처럼 주소가 바깥에서 바뀌면 폼을 새 값으로 다시 그린다.
        key={`${search.from}~${search.to}`}
        period={search}
        onSubmit={(period) =>
          navigate({ search: (prev) => ({ ...prev, ...period }) })
        }
      />
    </>
  );
}
