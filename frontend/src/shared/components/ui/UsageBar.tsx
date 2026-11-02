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
}: {
  usage: UsageView;
  size?: keyof typeof TRACK_CLASS;
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
        className={`flex-1 rounded-full ${TRACK_CLASS[size]}`}
      >
        <div
          className={`h-full rounded-full ${FILL_CLASS[usage.status]}`}
          // 너비는 서버가 준 사용률에서 정해지므로 inline style로 둔다.
          style={{ width: `${fill}%` }}
        />
      </div>
      <span
        className={`w-11 text-right ${usage.status === "over" ? "font-semibold text-red-600" : ""}`}
      >
        {label}
      </span>
    </div>
  );
}
