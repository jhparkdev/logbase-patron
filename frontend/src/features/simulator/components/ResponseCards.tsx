import { Button } from "../../../shared/components/ui/Button";
import type { SlotView } from "../lib/presentation";
import { CostValue, durationLabel, ExecutionStatus } from "./ResultValues";

export function ResponseCards({
  slots,
  onOpen,
  onCancel,
  cancelling,
}: {
  slots: SlotView[];
  onOpen: (slot: SlotView) => void;
  onCancel?: (key: string) => void;
  cancelling: (key: string) => boolean;
}) {
  return (
    <div className="grid grid-cols-1 items-start gap-4 @min-[32rem]:grid-cols-2 @min-[72rem]:grid-cols-4">
      {slots.map((slot) => (
        <article
          key={slot.key}
          className="flex min-w-0 flex-col gap-4 rounded-2xl bg-white p-5"
        >
          <div>
            <h3 className="break-words font-semibold">{slot.name}</h3>
            <p className="mt-1 break-words text-caption text-grey-600">
              {slot.provider}
            </p>
          </div>
          <div className="flex flex-wrap items-center justify-between gap-2">
            <ExecutionStatus status={slot.status} />
            <span className="text-caption text-grey-600 tabular-nums">
              {durationLabel(slot.durationMs)}
            </span>
          </div>
          <div className="flex items-center justify-between rounded-lg bg-grey-50 p-3 text-body-sm">
            <span className="text-grey-600">비용</span>
            <CostValue cost={slot.cost} />
          </div>
          {(slot.actualModel || slot.actualProvider) && (
            <p className="break-words text-caption text-grey-600">
              실제 처리: {slot.actualModel ?? slot.name} ·{" "}
              {slot.actualProvider ?? "미확인"}
            </p>
          )}
          {slot.comparisonNote && (
            <p className="text-caption text-yellow-900">
              {slot.comparisonNote}
            </p>
          )}
          <div>
            <p className="mb-2 text-label font-semibold">응답 내용</p>
            <div className="max-h-36 overflow-hidden whitespace-pre-wrap break-words rounded-lg bg-grey-50 p-3 text-body-sm text-grey-700">
              {slot.response === null
                ? "아직 응답을 받지 못했어요."
                : slot.response === ""
                  ? "빈 응답을 받았어요."
                  : slot.response}
            </div>
          </div>
          {slot.errorMessage && (
            <p className="rounded-lg bg-danger-weak p-3 text-body-sm text-red-600">
              {slot.errorMessage}
            </p>
          )}
          {!!slot.missingFields?.length && (
            <p className="text-caption text-red-600">
              누락된 필드: {slot.missingFields.join(", ")}
            </p>
          )}
          <div className="flex flex-wrap gap-2">
            <Button
              variant="secondary"
              size="sm"
              aria-label={`${slot.name} · ${slot.provider} 전체 응답 보기`}
              disabled={slot.response === null}
              onClick={() => onOpen(slot)}
            >
              전체 응답 보기
            </Button>
            {slot.status.ongoing && (
              <Button
                variant="secondary"
                size="sm"
                aria-label={`${slot.name} · ${slot.provider} 실행 취소`}
                disabled={!onCancel || cancelling(slot.key)}
                onClick={() => onCancel?.(slot.key)}
              >
                {cancelling(slot.key) ? "취소 요청 중" : "실행 취소"}
              </Button>
            )}
          </div>
        </article>
      ))}
    </div>
  );
}
