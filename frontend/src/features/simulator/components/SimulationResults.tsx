import { useState } from "react";
import { Button } from "../../../shared/components/ui/Button";
import { RefreshingBar } from "../../../shared/components/ui/RefreshingBar";
import { Result } from "../../../shared/components/ui/Result";
import { SectionCard } from "../../../shared/components/ui/SectionCard";
import { Skeleton } from "../../../shared/components/ui/Skeleton";
import { formatKstDateTime } from "../../../shared/lib/format";
import { useCancellation } from "../hooks/useCancellation";
import type { ResultSort, ResultsView, SlotView } from "../lib/presentation";
import { ResponseCards } from "./ResponseCards";
import { ResultTable } from "./ResultTable";
import { durationLabel } from "./ResultValues";
import { RunSummary } from "./RunSummary";
import { SimulatorDialog } from "./SimulatorDialog";

export type SimulationResultsProps = {
  view: ResultsView;
  sort?: ResultSort;
  onSort?: (sort: ResultSort) => void;
  onRefresh?: () => void;
  onCancelAll?: (runKey: string) => void | Promise<void>;
  onCancelSlot?: (runKey: string, slotKey: string) => void | Promise<void>;
};
export function SimulationResults({
  view,
  sort,
  onSort,
  onRefresh,
  onCancelAll,
  onCancelSlot,
}: SimulationResultsProps) {
  const [opened, setOpened] = useState<{ runKey: string; slot: SlotView }>();
  const cancellation = useCancellation();
  if (view.kind !== "ready")
    return (
      <SectionCard title="시뮬레이션 결과">
        {view.kind === "loading" ? (
          <div className="px-6 pb-6">
            <p role="status" className="mb-3 text-body-sm text-grey-600">
              실행 결과를 불러오고 있습니다
            </p>
            <Skeleton className="h-24 w-full" />
          </div>
        ) : (
          <Result
            title={
              view.kind === "error"
                ? "실행 결과를 불러오지 못했습니다"
                : "아직 실행 결과가 없습니다"
            }
            description={
              view.kind === "error"
                ? "잠시 후 다시 시도하시기 바랍니다."
                : "비교를 실행하면 모델별 응답과 비용을 확인할 수 있습니다."
            }
            action={
              view.kind === "error" && onRefresh ? (
                <Button variant="secondary" onClick={onRefresh}>
                  다시 시도
                </Button>
              ) : undefined
            }
          />
        )}
      </SectionCard>
    );
  const { run } = view;
  const allKey = `${run.key}:all`;
  const cancelling = (key: string) =>
    cancellation.pending.includes(allKey) ||
    cancellation.pending.includes(`${run.key}:${key}`);
  return (
    <section
      aria-labelledby="sim-results-title"
      className="@container flex flex-col gap-5"
    >
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 id="sim-results-title" className="text-section font-bold">
            시뮬레이션 결과 요약
          </h2>
          <p className="mt-1 text-caption text-grey-600 tabular-nums">
            실행 일시 {formatKstDateTime(run.requestedAt)} KST · 전체 실행 시간{" "}
            {durationLabel(run.durationMs)}
          </p>
        </div>
        <div className="flex gap-2">
          {run.status.ongoing && (
            <Button
              variant="secondary"
              size="sm"
              disabled={
                !onCancelAll ||
                cancellation.pending.some((key) =>
                  key.startsWith(`${run.key}:`),
                )
              }
              onClick={() =>
                onCancelAll &&
                void cancellation.send(allKey, () => onCancelAll(run.key))
              }
            >
              {cancellation.pending.includes(allKey)
                ? "취소 요청 중"
                : "전체 취소"}
            </Button>
          )}
          {onRefresh && (
            <Button
              variant="secondary"
              size="sm"
              disabled={view.refreshing}
              onClick={onRefresh}
            >
              다시 조회
            </Button>
          )}
        </div>
      </div>
      {cancellation.error && (
        <p role="alert" className="text-body-sm text-red-600">
          {cancellation.error}
        </p>
      )}
      <RunSummary run={run} />
      <div className="relative">
        {view.refreshing && <RefreshingBar />}
        <ResultTable slots={run.slots} sort={sort} onSort={onSort} />
      </div>
      <ResponseCards
        slots={run.slots}
        onOpen={(slot) => setOpened({ runKey: run.key, slot })}
        onCancel={
          onCancelSlot
            ? (slotKey) =>
                void cancellation.send(`${run.key}:${slotKey}`, () =>
                  onCancelSlot(run.key, slotKey),
                )
            : undefined
        }
        cancelling={cancelling}
      />
      {run.status.ongoing && (
        <p className="text-caption text-grey-600">
          취소 요청 후에도 처리 중인 호출의 비용이 발생할 수 있습니다. 최종
          상태와 비용을 확인하시기 바랍니다.
        </p>
      )}
      <SimulatorDialog
        open={!!opened && opened.runKey === run.key}
        title={
          opened
            ? `${opened.slot.name} · ${opened.slot.provider} 전체 응답`
            : "전체 응답"
        }
        onClose={() => setOpened(undefined)}
      >
        <pre className="max-h-96 overflow-auto whitespace-pre-wrap break-words rounded-lg bg-grey-50 p-4 text-body-sm">
          {opened?.slot.response}
        </pre>
      </SimulatorDialog>
    </section>
  );
}
