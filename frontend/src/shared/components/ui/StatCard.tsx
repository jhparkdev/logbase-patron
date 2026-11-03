import { HelpTip } from "./HelpTip";
import { Icon } from "./Icon";

const ICON_TONE_CLASS = {
  blue: "bg-blue-50 text-blue-500",
  green: "bg-green-50 text-green-600",
  purple: "bg-purple-50 text-purple-500",
  yellow: "bg-yellow-200 text-yellow-900",
  grey: "bg-grey-100 text-grey-600",
} as const;

const TREND = {
  up: { arrow: "▲", word: "증가", className: "text-delta-up" },
  down: { arrow: "▼", word: "감소", className: "text-delta-down" },
} as const;

type StatCardProps = {
  label: string;
  /** 표시 함수로 이미 포맷한 값. 예: "1,482", "126.50" */
  value: string;
  /** 값 뒤에 작게 붙는 단위. 예: "USD" */
  unit?: string;
  /** 없으면 아이콘 자리만 둔다. */
  icon?: string;
  iconTone?: keyof typeof ICON_TONE_CLASS;
  help?: string;
  trend?: { direction: keyof typeof TREND; rate: string };
  /** 증감 뒤에 붙는 비교 기준 */
  trendLabel?: string;
  caption?: string;
  /** 비용 미확인처럼 눈에 띄어야 하는 카드 */
  warning?: boolean;
};

export function StatCard({
  label,
  value,
  unit,
  icon,
  iconTone = "grey",
  help,
  trend,
  trendLabel = "전월 대비",
  caption,
  warning = false,
}: StatCardProps) {
  return (
    <div
      className={`flex gap-4 rounded-2xl p-5 ${warning ? "bg-warning-weak text-yellow-900" : "bg-white"}`}
    >
      <span
        className={`grid size-11 shrink-0 place-items-center rounded-full ${ICON_TONE_CLASS[warning ? "yellow" : iconTone]}`}
      >
        {icon && <Icon src={icon} className="size-5" />}
      </span>
      <div className="flex min-w-0 flex-col gap-1">
        <p
          className={`flex items-center gap-1 text-label font-medium ${warning ? "" : "text-grey-600"}`}
        >
          {label}
          {help && <HelpTip text={help} />}
        </p>
        <p className="text-title font-bold tabular-nums">
          {value}
          {unit && (
            <span className="ml-1 text-label font-semibold text-grey-600">
              {unit}
            </span>
          )}
        </p>
        {trend && <TrendText {...trend} label={trendLabel} />}
        {caption && <p className="text-caption text-grey-600">{caption}</p>}
      </div>
    </div>
  );
}

function TrendText({
  direction,
  rate,
  label,
}: NonNullable<StatCardProps["trend"]> & { label: string }) {
  const { arrow, word, className } = TREND[direction];
  return (
    <p className="text-label text-grey-600">
      <span className={`font-semibold ${className}`}>
        <span aria-hidden="true">{arrow}</span>
        {rate}
        <span className="sr-only"> {word}</span>
      </span>{" "}
      {label}
    </p>
  );
}
