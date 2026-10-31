import { createFileRoute } from "@tanstack/react-router";
import { UsageFilters } from "../../features/customer-usage/components/UsageFilters";
import { customerUsageSearchSchema } from "../../features/customer-usage/lib/search";
import { PageHeader } from "../../shared/components/ui/PageHeader";

export const Route = createFileRoute("/_app/customer-usage")({
  validateSearch: customerUsageSearchSchema,
  component: CustomerUsagePage,
});

function CustomerUsagePage() {
  const { from, to } = Route.useSearch();
  const navigate = Route.useNavigate();

  return (
    <>
      <PageHeader
        title="고객 AI 사용 현황"
        description="고객별 AI 이용 및 비용 현황을 한눈에 확인할 수 있어요."
      />
      <UsageFilters
        // 뒤로 가기처럼 주소가 바깥에서 바뀌면 폼을 새 값으로 다시 그린다.
        key={`${from}~${to}`}
        period={{ from, to }}
        onSubmit={(period) =>
          navigate({ search: (prev) => ({ ...prev, ...period }) })
        }
      />
    </>
  );
}
