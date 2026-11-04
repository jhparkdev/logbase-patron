import { Badge } from "../../../shared/components/ui/Badge";
import { Button } from "../../../shared/components/ui/Button";
import { Skeleton } from "../../../shared/components/ui/Skeleton";
import type { SlotView } from "../lib/presentation";
import { CostValue, durationLabel, ExecutionStatus } from "./ResultValues";

const VALIDATION_TONE: Record<string, "green" | "red" | "grey"> = {
  성공: "green",
  실패: "red",
};

function ResponseBody({
  slot,
  expanded,
}: {
  slot: SlotView;
  expanded: boolean;
}) {
  if (slot.response === null && slot.status.ongoing)
    return (
      <div className="flex flex-col gap-2.5 rounded-lg bg-grey-50 p-3.5">
        <p className="sr-only">응답을 기다리고 있어요</p>
        <Skeleton className="h-3 w-11/12" />
        <Skeleton className="h-3 w-3/4" />
        <Skeleton className="h-3 w-5/6" />
        <Skeleton className="h-3 w-1/2" />
      </div>
    );
  return (
    <div
      className={`whitespace-pre-wrap text-wrap rounded-lg bg-grey-50 p-3 text-body-sm text-grey-700 ${expanded ? "" : "max-h-80 overflow-y-auto"}`}
    >
      {slot.response === null
        ? "아직 응답을 받지 못했어요."
        : slot.response === ""
          ? "빈 응답을 받았어요."
          : slot.response}
    </div>
  );
}

/**
 * 모델별 응답을 나란히 둔다. 카드 폭을 고정해 모델이 많으면 가로로 스크롤한다.
 * 응답은 자르지 않고, 펼치기 전에는 카드 안에서 스크롤한다.
 */
export function ResponseCards({
  slots,
  expanded = false,
  onOpen,
  onCancel,
  cancelling,
}: {
  slots: SlotView[];
  expanded?: boolean;
  onOpen: (slot: SlotView) => void;
  onCancel?: (key: string) => void;
  cancelling: (key: string) => boolean;
}) {
  return (
    <div className="flex items-stretch gap-4 overflow-x-auto pb-2">
      {slots.map((slot) => (
        <article
          key={slot.key}
          className={`flex min-w-100 flex-1 flex-col gap-3 rounded-2xl p-5 ${slot.status.tone === "yellow" ? "bg-yellow-50/60" : slot.status.tone === "red" ? "bg-red-50/60" : "bg-white"}`}
        >
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0">
              <h3 className="font-semibold">{slot.name}</h3>
              <p className="mt-0.5 text-caption text-grey-600">
                {slot.provider}
              </p>
            </div>
            <div className="flex shrink-0 items-center gap-2">
              {slot.status.ongoing && (
                <span
                  role="status"
                  aria-label={`${slot.name} 실행 중`}
                  className="size-4 shrink-0 rounded-full border-2 border-grey-200 border-t-brand motion-safe:animate-spin"
                />
              )}
              <ExecutionStatus status={slot.status} />
            </div>
          </div>
          <div className="flex flex-wrap items-center justify-between gap-2 text-caption text-grey-600 tabular-nums">
            <span>
              {slot.status.ongoing
                ? "응답을 기다리는 중"
                : `응답 ${durationLabel(slot.durationMs)}`}
            </span>
            <span className="flex items-center gap-1.5">
              비용
              {slot.status.ongoing ? (
                <>
                  <span className="text-grey-900">—</span>
                  <span>응답 후 집계</span>
                </>
              ) : (
                <span className="text-grey-900">
                  <CostValue cost={slot.cost} />
                </span>
              )}
            </span>
          </div>
          {slot.statusAtRun && (
            <p className="text-caption text-grey-600">
              실행 당시 모델 상태: {slot.statusAtRun}
            </p>
          )}
          {slot.settings && (
            <div className="border-t border-grey-100 pt-2.5">
              <p className="mb-1 text-label font-semibold">적용 설정</p>
              {slot.settings.length ? (
                <dl className="space-y-1 text-caption text-grey-600">
                  {slot.settings.map((setting) => (
                    <div
                      key={setting.label}
                      className="flex justify-between gap-3"
                    >
                      <dt>{setting.label}</dt>
                      <dd className="min-w-0 text-right tabular-nums">
                        {setting.value}
                      </dd>
                    </div>
                  ))}
                </dl>
              ) : (
                <p className="text-caption text-grey-600">모델 기본값</p>
              )}
            </div>
          )}
          {(slot.actualModel || slot.actualProvider) && (
            <p className="text-caption text-grey-600">
              실제 처리: {slot.actualModel ?? slot.name} ·{" "}
              {slot.actualProvider ?? "미확인"}
            </p>
          )}
          {slot.comparisonNote && (
            <p className="text-caption text-yellow-900">
              {slot.comparisonNote}
            </p>
          )}
          <ResponseBody slot={slot} expanded={expanded} />
          <div className="flex flex-wrap gap-1.5">
            <Badge tone={VALIDATION_TONE[slot.jsonValidation] ?? "grey"}>
              {`JSON ${slot.jsonValidation}`}
            </Badge>
            <Badge tone={VALIDATION_TONE[slot.schemaValidation] ?? "grey"}>
              {`Schema ${slot.schemaValidation}`}
            </Badge>
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
          <div className="mt-auto flex flex-wrap gap-2 pt-1">
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
