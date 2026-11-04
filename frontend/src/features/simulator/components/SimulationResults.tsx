import { useState } from "react";
import { Button } from "../../../shared/components/ui/Button";
import { RefreshingBar } from "../../../shared/components/ui/RefreshingBar";
import { Result } from "../../../shared/components/ui/Result";
import { SectionCard } from "../../../shared/components/ui/SectionCard";
import { Skeleton } from "../../../shared/components/ui/Skeleton";
import { formatCount, formatKstDateTime } from "../../../shared/lib/format";
import { useCancellation } from "../hooks/useCancellation";
import type { ResultSort, ResultsView, SlotView } from "../lib/presentation";
import { bestSlotKeys } from "../lib/run-progress";
import { ResponseCards } from "./ResponseCards";
import { ResultTable } from "./ResultTable";
import { durationLabel, ExecutionStatus } from "./ResultValues";
import { RunProgress } from "./RunProgress";
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
  const [expanded, setExpanded] = useState(false);
  const cancellation = useCancellation();
  if (view.kind !== "ready")
    return (
      <SectionCard title="비교 결과">
        {view.kind === "loading" ? (
          <div className="px-6 pb-6">
            <p role="status" className="mb-3 text-body-sm text-grey-600">
              실행 결과를 불러오고 있어요
            </p>
            <Skeleton className="h-24 w-full" />
          </div>
        ) : (
          <Result
            title={
              view.kind === "error"
                ? "실행 결과를 불러오지 못했어요"
                : "아직 실행 결과가 없어요"
            }
            description={
              view.kind === "error"
                ? "잠시 후 다시 시도해 주세요."
                : "비교를 실행하면 모델별 응답과 비용을 나란히 볼 수 있어요."
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
  const best = run.status.ongoing
    ? { fastest: [], cheapest: [] }
    : bestSlotKeys(run.slots);
  return (
    <section
      aria-labelledby="sim-results-title"
      className="flex flex-col gap-5"
    >
      <div className="flex flex-wrap items-center gap-3">
        <h2 id="sim-results-title" className="text-section font-bold">
          비교 결과
        </h2>
        <ExecutionStatus status={run.status} />
        <p className="text-caption text-grey-600 tabular-nums">
          실행 일시 {formatKstDateTime(run.requestedAt)} KST · 전체{" "}
          {durationLabel(run.durationMs)} · {formatCount(run.modelCount)}개 모델
        </p>
        <div className="ml-auto flex gap-2">
          {run.status.ongoing && (
            <Button
              variant="secondary"
              size="sm"
              className="text-red-600"
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
      {run.status.ongoing && <RunProgress slots={run.slots} />}
      <RunSummary run={run} />
      <SectionCard
        title="숫자로 비교"
        description="머리글을 누르면 정렬돼요. 값이 없는 칸은 맨 뒤로 가요."
      >
        <div className="relative">
          {view.refreshing && <RefreshingBar />}
          <ResultTable
            slots={run.slots}
            sort={sort}
            onSort={onSort}
            best={best}
          />
        </div>
      </SectionCard>
      <div className="flex flex-col gap-3">
        <div className="flex flex-wrap items-center gap-3">
          <h3 className="text-section font-bold">응답으로 비교</h3>
          <p className="text-caption text-grey-600">
            같은 입력에 대한 응답을 나란히 봐요. 모델이 많으면 옆으로 넘겨요.
          </p>
          <Button
            variant="secondary"
            size="sm"
            className="ml-auto"
            aria-pressed={expanded}
            onClick={() => setExpanded(!expanded)}
          >
            {expanded ? "응답 접기" : "응답 전체 펼치기"}
          </Button>
        </div>
        <ResponseCards
          slots={run.slots}
          expanded={expanded}
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
      </div>
      <SimulatorDialog
        open={!!opened && opened.runKey === run.key}
        title={
          opened
            ? `${opened.slot.name} · ${opened.slot.provider} 전체 응답`
            : "전체 응답"
        }
        onClose={() => setOpened(undefined)}
      >
        <pre className="max-h-96 overflow-auto whitespace-pre-wrap text-wrap rounded-lg bg-grey-50 p-4 text-body-sm">
          {opened?.slot.response}
        </pre>
      </SimulatorDialog>
    </section>
  );
}
