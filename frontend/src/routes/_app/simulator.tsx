import { createFileRoute } from "@tanstack/react-router";
import { PageHeader } from "../../shared/components/ui/PageHeader";

export const Route = createFileRoute("/_app/simulator")({
  component: () => <PageHeader title="AI 모델 시뮬레이터" />,
});
