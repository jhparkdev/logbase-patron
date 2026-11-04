import type { SlotView } from "../lib/presentation";
import type { ProgressTone } from "../lib/run-progress";
import { runProgress } from "../lib/run-progress";

const SEGMENT_CLASS: Record<ProgressTone, string> = {
  green: "bg-green-500",
  yellow: "bg-yellow-800",
  red: "bg-red-500",
  grey: "bg-grey-400",
  brand: "bg-brand motion-safe:animate-pulse",
};

/** 실행 중에만 보이는 진행 띠. 몇 개 중 몇 개가 끝났는지를 한눈에 보여 준다. */
export function RunProgress({ slots }: { slots: readonly SlotView[] }) {
  const progress = runProgress(slots);
  return (
    <section
      aria-live="polite"
      className="flex flex-col gap-3.5 rounded-2xl border border-blue-100 bg-blue-50 px-6 py-5"
    >
      <div className="flex flex-wrap items-center gap-3">
        <span
          role="status"
          aria-label="실행 중"
          className="size-4 shrink-0 rounded-full border-2 border-grey-200 border-t-brand motion-safe:animate-spin"
        />
        <h3 className="text-section font-bold">
          실행 중 ·{" "}
          <span className="tabular-nums">
            {progress.total}개 중 {progress.done}개
          </span>{" "}
          완료
        </h3>
        <span className="text-caption text-grey-600">
          응답이 오는 대로 자동으로 갱신해요
        </span>
      </div>
      <div
        aria-hidden="true"
        className="grid gap-1.5"
        style={{
          gridTemplateColumns: `repeat(${progress.total}, minmax(0, 1fr))`,
        }}
      >
        {progress.tones.map((tone, index) => (
          <span
            // 칸 순서가 곧 모델 칸 순서라 위치가 바뀌지 않는다
            key={slots[index]?.key ?? index}
            className={`h-2 rounded-full ${SEGMENT_CLASS[tone]}`}
          />
        ))}
      </div>
      <p className="text-caption text-grey-600">
        취소해도 이미 처리 중인 호출의 비용은 발생할 수 있어요. 끝난 뒤 최종
        상태와 비용을 확인해 주세요.
      </p>
    </section>
  );
}
