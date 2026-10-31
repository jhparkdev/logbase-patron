import { Button } from "../../../shared/components/ui/Button";
import { SectionCard } from "../../../shared/components/ui/SectionCard";
import { formatCount, formatKstDateTime } from "../../../shared/lib/format";
import type { HistoryRow } from "../lib/presentation";
import { HistoryCost, HistoryCostStatus, HistoryStatus } from "./HistoryValues";

export function HistorySummary({
  row,
  onOpen,
}: {
  row: HistoryRow;
  onOpen: () => void;
}) {
  return (
    <SectionCard
      title="선택한 실행 결과 요약"
      action={
        <Button variant="secondary" size="sm" onClick={onOpen}>
          상세 결과 보기
        </Button>
      }
    >
      <div className="px-6 pb-6">
        <p className="mb-4 break-all text-body-sm font-semibold text-blue-600">
          {row.key}
        </p>
        <dl className="grid grid-cols-3 gap-4 2xl:grid-cols-6">
          <div>
            <dt className="text-label text-grey-600">실행 시각</dt>
            <dd className="mt-1 text-body-sm tabular-nums">
              {formatKstDateTime(row.requestedAt)}
            </dd>
          </div>
          <div>
            <dt className="text-label text-grey-600">시나리오</dt>
            <dd className="mt-1 text-body-sm">{row.scenario}</dd>
          </div>
          <div>
            <dt className="text-label text-grey-600">모델 수</dt>
            <dd className="mt-1 tabular-nums">
              {formatCount(row.modelCount)}개
            </dd>
          </div>
          <div>
            <dt className="text-label text-grey-600">실행 상태</dt>
            <dd className="mt-1">
              <HistoryStatus status={row.status} />
            </dd>
          </div>
          <div>
            <dt className="text-label text-grey-600">비용 상태</dt>
            <dd className="mt-1">
              <HistoryCostStatus cost={row.cost} />
            </dd>
          </div>
          <div>
            <dt className="text-label text-grey-600">총 비용 (USD)</dt>
            <dd className="mt-1">
              <HistoryCost cost={row.cost} />
            </dd>
          </div>
        </dl>
        {row.inactiveModelCount !== null && row.inactiveModelCount > 0 && (
          <p className="mt-5 rounded-lg bg-warning-weak p-3 text-body-sm text-yellow-900">
            현재 선택할 수 없는 모델이 {formatCount(row.inactiveModelCount)}개
            포함되어 있어요. 과거 결과는 유지되며, 재실행 전에 모델을 교체하거나
            제외해 주세요.
          </p>
        )}
      </div>
    </SectionCard>
  );
}
