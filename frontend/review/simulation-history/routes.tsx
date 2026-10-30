import {
  createRootRoute,
  createRoute,
  createRouter,
  defaultStringifySearch,
  redirect,
  useRouter,
} from "@tanstack/react-router";
import { z } from "zod";
import { HistoryPage } from "../../src/features/simulation-history/components/HistoryPage";
import { createHistorySearchSchema } from "../../src/features/simulation-history/lib/search";
import { dbMock } from "../../src/features/simulator/components/dbMock.fixture";
import { SimulationResults } from "../../src/features/simulator/components/SimulationResults";
import { SimulatorRestore } from "../../src/features/simulator/components/SimulatorRestore";
import { Button } from "../../src/shared/components/ui/Button";
import { PAGE_SIZE, pageCount } from "../../src/shared/lib/pagination";
import { HistoryPreviewLayout } from "./PreviewLayout";
import {
  historyDetail,
  rerunSnapshot,
  selectPreviewRows,
} from "./preview-data.fixture";

const previewSearch = createHistorySearchSchema(
  new Date("2026-10-29T00:00:00Z"),
).and(
  z.object({ rerun: z.string().min(1).max(128).optional().catch(undefined) }),
);
const root = createRootRoute({
  beforeLoad: ({ location }) => {
    if (location.pathname !== "/simulation-history-preview.html")
      throw redirect({ href: location.href, reloadDocument: true });
  },
});
const previewRoute = createRoute({
  getParentRoute: () => root,
  path: "/simulation-history-preview.html",
  validateSearch: previewSearch,
  beforeLoad: ({ search }) => {
    if (search.rerun) return;
    const lastPage = pageCount(selectPreviewRows(search).length, PAGE_SIZE);
    if (search.page > lastPage)
      throw redirect({
        href: `/simulation-history-preview.html${defaultStringifySearch({ ...search, page: lastPage })}`,
        replace: true,
      });
  },
  component: HistoryPreview,
});
export const historyPreviewTree = root.addChildren([previewRoute]);
export function createHistoryPreviewRouter() {
  return createRouter({ routeTree: historyPreviewTree });
}
type PreviewRouter = ReturnType<typeof createHistoryPreviewRouter>;

function HistoryPreview() {
  const search = previewRoute.useSearch<PreviewRouter>();
  return (
    <HistoryPreviewLayout
      activeTo={search.rerun ? "/simulator" : "/simulation-history"}
    >
      <HistoryPreviewContent search={search} />
    </HistoryPreviewLayout>
  );
}

function HistoryPreviewContent({
  search,
}: {
  search: z.output<typeof previewSearch>;
}) {
  const router = useRouter<PreviewRouter>();
  const updateSearch = (next: z.output<typeof previewSearch>) => {
    void router.navigate({
      href: `/simulation-history-preview.html${defaultStringifySearch(next)}`,
      resetScroll: search.rerun !== next.rerun,
    });
  };
  if (search.rerun) {
    const values = rerunSnapshot(search.rerun);
    return (
      <>
        <div>
          <Button
            variant="secondary"
            onClick={() => {
              updateSearch({ ...search, rerun: undefined, detail: true });
            }}
          >
            이력으로 돌아가기
          </Button>
        </div>
        <SimulatorRestore
          sourceKey={search.rerun}
          view={
            values
              ? {
                  kind: "ready",
                  key: search.rerun,
                  values,
                  choices: dbMock.choices,
                  scenarios: dbMock.scenarios,
                }
              : { kind: "missing" }
          }
        />
      </>
    );
  }
  const rows = selectPreviewRows(search);
  const start = (search.page - 1) * PAGE_SIZE;
  const detail = search.selected ? historyDetail(search.selected) : undefined;
  return (
    <HistoryPage
      search={search}
      onSearch={(next) => {
        updateSearch({ ...next, rerun: undefined });
      }}
      view={{
        kind: "ready",
        items: rows.slice(start, start + PAGE_SIZE),
        total: rows.length,
      }}
      detail={detail ? { kind: "ready", value: detail } : { kind: "missing" }}
      scenarios={dbMock.scenarios}
      models={dbMock.choices.map((choice) => ({
        key: choice.key,
        name: `${choice.name} · ${choice.provider}`,
      }))}
      onRerun={(key) => {
        updateSearch({ ...search, detail: false, rerun: key });
      }}
      renderResults={(key) => {
        const run = dbMock.runs.find((run) => run.key === key);
        return run ? <SimulationResults view={{ kind: "ready", run }} /> : null;
      }}
    />
  );
}
