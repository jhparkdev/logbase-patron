import { useState } from "react";
import warningIcon from "../../../assets/warning.svg";
import { Icon } from "../../../shared/components/ui/Icon";
import type { ModelDetail } from "../api/models";
import {
  type ChangeableStatus,
  statusNotices,
  statusSegments,
  timeOrNone,
} from "../lib/view";
import { StatusChangeDialog } from "./StatusChangeDialog";

// 상태 전환 칸. 규격은 docs/design/tokens.md "상태 전환 칸"
const SEGMENT_CLASS =
  "inline-flex h-9 items-center justify-center gap-1.5 rounded-lg text-label font-semibold transition-colors focus-visible:outline-2 focus-visible:outline-brand";
const SEGMENT_STATE_CLASS = {
  selected: "bg-white text-grey-900 shadow-sm",
  enabled: "text-grey-600 hover:text-grey-900",
  disabled: "cursor-not-allowed text-grey-400",
} as const;
const DOT_CLASS = {
  blue: "bg-blue-500",
  green: "bg-green-500",
  grey: "bg-grey-400",
} as const;
const IDLE_DOT_CLASS = "bg-grey-300";

/** 상태 전환 칸 세 개, 누르면 생기는 일 안내, 활성화·비활성화 시각. 칸을 누르면 확인창을 거침 */
export function ModelStatusControls({ model }: { model: ModelDetail }) {
  // 확인창을 연 대상 상태. 없으면 창이 닫힌 상태
  const [target, setTarget] = useState<ChangeableStatus>();
  return (
    <>
      <fieldset className="grid grid-cols-3 gap-1 rounded-xl bg-grey-100 p-1">
        <legend className="sr-only">운영 상태</legend>
        {statusSegments(model.status).map((segment) => (
          <button
            type="button"
            key={segment.status}
            aria-pressed={segment.selected}
            disabled={segment.disabled}
            onClick={() => {
              if (segment.status !== "TESTING") setTarget(segment.status);
            }}
            className={`${SEGMENT_CLASS} ${
              SEGMENT_STATE_CLASS[
                segment.selected
                  ? "selected"
                  : segment.disabled
                    ? "disabled"
                    : "enabled"
              ]
            }`}
          >
            <span
              aria-hidden="true"
              className={`size-1.5 rounded-full ${segment.selected ? DOT_CLASS[segment.tone] : IDLE_DOT_CLASS}`}
            />
            {segment.label}
          </button>
        ))}
      </fieldset>
      <div className="flex gap-3 rounded-2xl bg-warning-weak p-4 text-body-sm text-yellow-900">
        <Icon src={warningIcon} className="mt-0.5 size-4 shrink-0" />
        <div className="flex flex-col gap-1">
          {statusNotices(model.status).map((notice) => (
            <p key={notice.label}>
              <strong>{notice.label}</strong>을 누르면 {notice.hint}
            </p>
          ))}
        </div>
      </div>
      <p className="text-caption text-grey-600 tabular-nums">
        활성화 {timeOrNone(model.activated_at)} · 비활성화{" "}
        {timeOrNone(model.deactivated_at)}
      </p>
      {target && (
        <StatusChangeDialog
          model={model}
          target={target}
          onClose={() => setTarget(undefined)}
        />
      )}
    </>
  );
}
