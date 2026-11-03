import type { CSSProperties } from "react";

/**
 * 막대가 처음 그려질 때 0에서 값까지 차오르고, 값이 바뀌면 그 값으로 옮겨 간다. 규격은 docs/design/tokens.md "모션".
 * 너비를 inline width로 주면 시작 상태(@starting-style)의 0이 밀리므로, CSS 변수로 넘기고 클래스로 그린다.
 */
export const BAR_FILL_CLASS =
  "w-(--fill) motion-safe:transition-[width] motion-safe:duration-500 motion-safe:ease-out motion-safe:starting:w-0";

/** 막대 너비(%)를 BAR_FILL_CLASS가 읽는 CSS 변수로 */
export function barFillStyle(percent: number): CSSProperties {
  return { "--fill": `${percent}%` } as CSSProperties;
}

/** 예산 사용률. 상태는 서버가 판정한 값을 그대로 받는다. 예산이 없으면 사용률이 없다. */
export type UsageView =
  | { status: "normal" | "warning" | "over"; percent: number }
  | { status: "unset" };

const FULL_PERCENT = 100;

const FILL_CLASS = {
  normal: "bg-green-500",
  warning: "bg-yellow-600",
  over: "bg-red-500",
} as const;

/** 표 안은 얇게(md), 상세 패널 요약처럼 회색 바탕 위에서 강조할 때는 두껍고 진하게(lg) 그린다. */
const TRACK_CLASS = {
  md: "h-1.5 bg-grey-100",
  lg: "h-2.5 bg-grey-200",
} as const;

export function UsageBar({
  usage,
  size = "md",
  warningAt,
}: {
  usage: UsageView;
  size?: keyof typeof TRACK_CLASS;
  /** 서버가 판정에 쓰는 주의 기준 사용률(%). 있으면 막대 위에 기준선을 둔다 */
  warningAt?: number;
}) {
  if (usage.status === "unset") {
    return <span className="text-grey-600">예산을 정하면 사용률이 보여요</span>;
  }
  const label = `${usage.percent}%`;
  // 100%를 넘으면 막대는 꽉 찬 채로 두고, 실제 사용률은 글자로 보여 준다.
  const fill = Math.min(usage.percent, FULL_PERCENT);
  return (
    <div className="flex items-center gap-2.5">
      {/* 기본 meter는 브라우저마다 모양이 달라, 화면 낭독기용으로만 두고 막대는 따로 그린다. */}
      <meter
        aria-label="사용률"
        aria-valuetext={label}
        min={0}
        max={FULL_PERCENT}
        value={fill}
        className="sr-only"
      />
      <div
        aria-hidden="true"
        className={`relative flex-1 rounded-full ${TRACK_CLASS[size]}`}
      >
        <div
          className={`h-full rounded-full ${FILL_CLASS[usage.status]} ${BAR_FILL_CLASS}`}
          style={barFillStyle(fill)}
        />
        {warningAt !== undefined && (
          <span
            data-mark="warning"
            className="absolute inset-y-0 w-0.5 -translate-x-1/2 bg-yellow-700"
            style={{ left: `${Math.min(warningAt, FULL_PERCENT)}%` }}
          />
        )}
      </div>
      <span
        className={`w-11 text-right ${usage.status === "over" ? "font-semibold text-red-600" : ""}`}
      >
        {label}
      </span>
    </div>
  );
}
