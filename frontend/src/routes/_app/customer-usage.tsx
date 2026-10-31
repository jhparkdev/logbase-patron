import { createFileRoute } from "@tanstack/react-router";
import { customerUsageSearchSchema } from "../../features/customer-usage/lib/search";
import { PageHeader } from "../../shared/components/ui/PageHeader";

export const Route = createFileRoute("/_app/customer-usage")({
  validateSearch: customerUsageSearchSchema,
  component: () => (
    <PageHeader
      title="고객 AI 사용 현황"
      description="고객별 AI 이용 및 비용 현황을 한눈에 확인할 수 있어요."
    />
  ),
});
