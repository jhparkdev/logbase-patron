import type { components } from "../../../shared/api/schema";
import { Badge } from "../../../shared/components/ui/Badge";
import {
  budgetStatusBadge,
  remainingBudget,
  usageView,
} from "../../../shared/lib/budget";
import { formatUsd } from "../../../shared/lib/format";
import {
  budgetSegments,
  type CostKey,
  costBreakdown,
  usageHeadline,
} from "../lib/project";

type Detail = components["schemas"]["ProjectUsageDetail"];

const FULL_PERCENT = 100;
const UNSET_BAR_LABEL = "예산을 정하면 사용률이 보여요";
// 구간 색. 규격은 docs/design/tokens.md "쌓은 진행 막대"
const SEGMENT_CLASS: Record<CostKey, string> = {
  confirmed: "bg-blue-500",
  estimated: "bg-blue-200",
  subscription: "bg-teal-500",
};
const AMOUNT_CLASS: Record<CostKey, string> = {
  confirmed: "",
  estimated: "text-blue-600",
  subscription: "",
};

/** 프로젝트 상세 패널 맨 위. 이번 달 사용액(구독료 포함)을 예산 대비 쌓은 막대로 보여 주고, 구성 금액을 나열한다. */
export function ProjectUsageSummary({
  month,
  detail,
}: {
  /** 예산을 비교하는 달 "YYYY-MM" */
  month: string;
  detail: Detail;
}) {
  const { budget } = detail;
  const badge = budgetStatusBadge(budget.status);
  const usage = usageView(budget);
  const segments = budgetSegments(detail);
  const remaining = remainingBudget(budget.remaining_usd);
  return (
    <section className="flex flex-col gap-4 rounded-2xl bg-grey-50 p-5">
      <div className="flex items-start justify-between gap-3">
        <div className="flex flex-col gap-1">
          <h3 className="text-label font-medium text-grey-600">
            {month} 사용액 · 추정·구독료 포함
          </h3>
          <p className="text-title font-bold tabular-nums">
            {formatUsd(budget.used_usd, "summary")}{" "}
            <span className="text-body font-medium text-grey-600">
              {budget.monthly_amount_usd === null
                ? "USD"
                : `/ ${formatUsd(budget.monthly_amount_usd, "summary")} USD`}
            </span>
          </p>
        </div>
        <Badge tone={badge.tone}>{badge.label}</Badge>
      </div>
      {segments && usage.status !== "unset" ? (
        <>
          <meter
            aria-label="사용률"
            aria-valuetext={`${usage.percent}%`}
            min={0}
            max={FULL_PERCENT}
            value={Math.min(usage.percent, FULL_PERCENT)}
            className="sr-only"
          />
          <div
            aria-hidden="true"
            className="flex h-2.5 overflow-hidden rounded-full bg-grey-200"
          >
            {segments.map((segment) => (
              <div
                key={segment.key}
                className={SEGMENT_CLASS[segment.key]}
                // 너비는 서버가 준 금액에서 정해지므로 inline style로 둔다.
                style={{ width: `${segment.width}%` }}
              />
            ))}
          </div>
        </>
      ) : (
        <p className="text-body-sm text-grey-600">{UNSET_BAR_LABEL}</p>
      )}
      <div className="flex items-baseline justify-between gap-3 text-body-sm tabular-nums">
        <span className="font-semibold">{usageHeadline(budget)}</span>
        {remaining && (
          <span className={remaining.over ? "text-red-600" : ""}>
            {remaining.label}{" "}
            <strong>{formatUsd(remaining.amount, "summary")}</strong>
          </span>
        )}
      </div>
      <ul className="flex flex-col gap-1.5 border-t border-grey-200 pt-3 text-body-sm tabular-nums">
        {costBreakdown(detail).map((cost) => (
          <li key={cost.key} className="flex items-center gap-2">
            <span
              aria-hidden="true"
              className={`size-2 shrink-0 rounded-xs ${SEGMENT_CLASS[cost.key]}`}
            />
            <span className="flex-1 text-grey-700">{cost.label}</span>
            <span className={`font-semibold ${AMOUNT_CLASS[cost.key]}`}>
              {cost.amount}
            </span>
          </li>
        ))}
      </ul>
    </section>
  );
}
