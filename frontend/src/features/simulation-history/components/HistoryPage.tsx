import type { ReactNode } from "react";
import { Button } from "../../../shared/components/ui/Button";
import { PageHeader } from "../../../shared/components/ui/PageHeader";
import { RefreshingBar } from "../../../shared/components/ui/RefreshingBar";
import { Result } from "../../../shared/components/ui/Result";
import { SectionCard } from "../../../shared/components/ui/SectionCard";
import { Skeleton } from "../../../shared/components/ui/Skeleton";
import type {
  HistoryDetailState,
  HistoryListView,
  HistoryOption,
} from "../lib/presentation";
import type { HistorySearch } from "../lib/search";
import { HistoryDetail } from "./HistoryDetail";
import { HistoryFilters } from "./HistoryFilters";
import { HistorySummary } from "./HistorySummary";
import { HistoryTable } from "./HistoryTable";

export function HistoryPage({
  search,
  onSearch,
  view = { kind: "unavailable" },
  detail = { kind: "unavailable" },
  scenarios = [],
  models = [],
  onRetry,
  onRetryDetail,
  onRerun,
  renderResults,
  pagination,
}: {
  search: HistorySearch;
  onSearch: (value: HistorySearch) => void;
  view?: HistoryListView;
  detail?: HistoryDetailState;
  scenarios?: readonly HistoryOption[];
  models?: readonly HistoryOption[];
  onRetry?: () => void;
  onRetryDetail?: () => void;
  onRerun?: (key: string) => void;
  renderResults?: (key: string) => ReactNode;
  /** P-03 담당자의 공통 페이지네이션을 라우트에서 연결할 자리다. */
  pagination?: ReactNode;
}) {
  const selected =
    view.kind === "ready"
      ? view.items.find((row) => row.key === search.selected)
      : undefined;
  const filterKey = JSON.stringify([
    search.from,
    search.to,
    search.scenario,
    search.model,
    search.status,
    search.simulationId,
  ]);
  return (
    <>
      <PageHeader title="시뮬레이션 결과 이력" />
      <p className="-mt-4 text-body-sm text-grey-600">
        과거 실행의 입력과 결과를 확인하고 같은 조건으로 새 비교를 준비할 수
        있어요.
      </p>
      <HistoryFilters
        key={filterKey}
        values={search}
        scenarios={scenarios}
        models={models}
        onSubmit={(filters) =>
          onSearch({
            ...search,
            ...filters,
            selected: undefined,
            detail: false,
          })
        }
      />
      <SectionCard
        title="시뮬레이션 이력 목록"
        count={view.kind === "ready" ? view.total : undefined}
        description="각 행은 모델별 호출을 묶은 하나의 실행이에요."
      >
        {view.kind === "ready" && view.refreshing && <RefreshingBar />}
        {view.kind === "loading" ? (
          <div className="px-6 pb-6">
            <p role="status" className="mb-3 text-body-sm text-grey-600">
              실행 이력을 불러오고 있어요
            </p>
            <Skeleton className="h-48 w-full" />
          </div>
        ) : view.kind === "ready" && view.items.length ? (
          <>
            <HistoryTable
              rows={view.items}
              search={search}
              onSearch={onSearch}
            />
            {pagination && <div className="p-5">{pagination}</div>}
          </>
        ) : (
          <Result
            title={
              view.kind === "unavailable"
                ? "이력 조회를 준비하고 있어요"
                : view.kind === "error"
                  ? "실행 이력을 불러오지 못했어요"
                  : "조건에 맞는 실행 이력이 없어요"
            }
            description={
              view.kind === "unavailable"
                ? "API가 연결되면 과거 실행을 조회할 수 있어요. 검색 조건은 미리 설정할 수 있어요."
                : view.kind === "error"
                  ? "잠시 후 다시 시도해 주세요."
                  : "조회 기간이나 검색 조건을 바꿔 다시 조회해 주세요."
            }
            action={
              view.kind === "error" && onRetry ? (
                <Button variant="secondary" onClick={onRetry}>
                  다시 시도
                </Button>
              ) : undefined
            }
          />
        )}
      </SectionCard>
      {selected && (
        <HistorySummary
          row={selected}
          onOpen={() => onSearch({ ...search, detail: true })}
        />
      )}
      <HistoryDetail
        selected={search.selected}
        open={!!search.selected && search.detail}
        state={detail}
        onClose={() => onSearch({ ...search, detail: false })}
        onRetry={onRetryDetail}
        onRerun={onRerun}
        renderResults={renderResults}
      />
    </>
  );
}
