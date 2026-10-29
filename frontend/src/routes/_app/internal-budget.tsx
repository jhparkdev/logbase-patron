import { createFileRoute } from "@tanstack/react-router";
import { PageHeader } from "../../shared/components/ui/PageHeader";

export const Route = createFileRoute("/_app/internal-budget")({
  component: () => <PageHeader title="내부 AI 예산 관리" />,
});
