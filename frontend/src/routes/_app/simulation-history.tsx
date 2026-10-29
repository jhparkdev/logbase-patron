import { createFileRoute } from "@tanstack/react-router";
import { HistoryPage } from "../../features/simulation-history/components/HistoryPage";
import { historySearchSchema } from "../../features/simulation-history/lib/search";

export const Route = createFileRoute("/_app/simulation-history")({
  validateSearch: historySearchSchema,
  component: HistoryRoute,
});

function HistoryRoute() {
  const search = Route.useSearch();
  const navigate = Route.useNavigate();
  return (
    <HistoryPage
      search={search}
      onSearch={(value) => {
        void navigate({ search: value });
      }}
      onRerun={(key) => {
        void navigate({
          to: "/simulator",
          search: { sourceRun: key, sort: "model", direction: "asc" },
        });
      }}
    />
  );
}
