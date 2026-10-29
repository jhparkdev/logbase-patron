import { createFileRoute } from "@tanstack/react-router";
import { PageHeader } from "../../shared/components/ui/PageHeader";

export const Route = createFileRoute("/_app/models")({
  component: () => <PageHeader title="AI 모델 관리" />,
});
