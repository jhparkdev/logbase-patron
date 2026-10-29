import resultIcon from "../../../assets/simulatorResult.svg";
import { StatCard } from "../../../shared/components/ui/StatCard";
import { formatCount, formatUsd } from "../../../shared/lib/format";
import type { RunView } from "../lib/presentation";

export function RunSummary({ run }: { run: RunView }) {
  return (
    <div>
      <div className="grid grid-cols-3 gap-3 2xl:grid-cols-6">
        <StatCard
          label="전체 상태"
          value={run.status.label}
          icon={resultIcon}
          caption={`${formatCount(run.modelCount)}개 모델 비교`}
        />
        <StatCard
          label="성공 모델"
          value={formatCount(run.successCount)}
          unit="개"
          icon={resultIcon}
          iconTone="green"
        />
        <StatCard
          label="실패·시간 초과"
          value={formatCount(run.failureCount)}
          unit="개"
          icon={resultIcon}
          iconTone="yellow"
        />
        <StatCard
          label="확정 비용"
          value={
            run.confirmedCost === null
              ? "집계 없음"
              : `$${formatUsd(run.confirmedCost, "summary")}`
          }
          icon={resultIcon}
          iconTone="blue"
        />
        <StatCard
          label="추정 비용"
          value={
            run.estimatedCost === null
              ? "집계 없음"
              : `≈ $${formatUsd(run.estimatedCost, "summary")}`
          }
          icon={resultIcon}
          iconTone="blue"
        />
        <StatCard
          label="미확인 비용"
          value={formatCount(run.unknownCostCount)}
          unit="건"
          icon={resultIcon}
          warning={run.unknownCostCount > 0}
        />
      </div>
      <div className="mt-3 flex flex-wrap items-center justify-end gap-x-4 gap-y-1 text-body-sm">
        <p>
          비교 비용 합계{" "}
          <span className="ml-2 font-semibold tabular-nums">
            {run.totalCost === null
              ? "미확인"
              : `${run.estimatedCost !== null ? "≈ " : ""}$${formatUsd(run.totalCost, "summary")}`}
          </span>
        </p>
        {run.estimatedCost !== null && (
          <span className="text-blue-600">추정 포함</span>
        )}
        {run.unknownCostCount > 0 && (
          <span className="text-yellow-900">
            미확인 {formatCount(run.unknownCostCount)}건 미반영
          </span>
        )}
      </div>
    </div>
  );
}
