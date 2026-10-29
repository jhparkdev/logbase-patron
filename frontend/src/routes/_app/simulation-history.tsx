import { createFileRoute } from "@tanstack/react-router";
import { PageHeader } from "../../shared/components/ui/PageHeader";

export const Route = createFileRoute("/_app/simulation-history")({
  component: () => <PageHeader title="시뮬레이션 결과 이력" />,
});
