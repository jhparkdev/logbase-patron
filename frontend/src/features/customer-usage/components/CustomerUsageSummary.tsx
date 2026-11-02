import type { ReactNode } from "react";
import type { components } from "../../../shared/api/schema";
import { Badge } from "../../../shared/components/ui/Badge";
import { UsageBar } from "../../../shared/components/ui/UsageBar";
import { budgetStatusBadge, usageView } from "../../../shared/lib/budget";
import {
  formatCount,
  formatUsd,
  isZeroAmount,
  unreflectedText,
} from "../../../shared/lib/format";
import { remainingBudget } from "../lib/panel";

type Detail = components["schemas"]["CustomerUsageDetail"];

const TILE_CLASS = {
  plain: { box: "border border-grey-100", value: "" },
  estimated: { box: "border border-grey-100", value: "text-blue-600" },
  warning: { box: "bg-warning-weak", value: "text-yellow-900" },
} as const;

/** 고객 상세 패널 맨 위. 이번 달 사용액과 예산 대비 상태를 크게 보여 주고, 아래에 확정·추정·미확인을 나눠 보여 준다. */
export function CustomerUsageSummary({
  month,
  detail,
}: {
  /** 예산을 비교하는 달 "YYYY-MM" */
  month: string;
  detail: Detail;
}) {
  const { budget } = detail;
  const badge = budgetStatusBadge(budget.status);
  const remaining = remainingBudget(budget.remaining_usd);
  const hasEstimate = !isZeroAmount(detail.estimated_cost_usd);
  const estimated = formatUsd(detail.estimated_cost_usd, "summary");
  const facts = [
    `작업 ${formatCount(detail.task_count)}건`,
    `호출 ${formatCount(detail.call_count)}회`,
    unreflectedText(detail.unknown_cost_count),
  ];
  return (
    <>
      <section className="flex flex-col gap-4 rounded-2xl bg-grey-50 p-5">
        <div className="flex items-start justify-between gap-3">
          <div className="flex flex-col gap-1">
            <h3 className="text-label font-medium text-grey-600">
              {month} 사용액 · 추정 포함
            </h3>
            <p className="text-title font-bold tabular-nums">
              {formatUsd(budget.used_usd, "summary")}{" "}
              <span className="text-body font-medium text-grey-600">USD</span>
            </p>
          </div>
          <Badge tone={badge.tone}>{badge.label}</Badge>
        </div>
        <UsageBar usage={usageView(budget)} size="lg" />
        {budget.monthly_amount_usd !== null && remaining && (
          <dl className="grid grid-cols-[1fr_auto] gap-y-1 border-t border-grey-200 pt-3 text-body-sm tabular-nums">
            <dt className="text-grey-700">월 예산</dt>
            <dd className="text-right">
              {formatUsd(budget.monthly_amount_usd, "summary")} USD
            </dd>
            <dt className="text-grey-700">{remaining.label}</dt>
            <dd
              className={`text-right font-bold ${remaining.over ? "text-red-600" : ""}`}
            >
              {formatUsd(remaining.amount, "summary")} USD
            </dd>
          </dl>
        )}
      </section>
      <section aria-label="비용 구분" className="flex flex-col gap-2.5">
        <div className="grid grid-cols-3 gap-2">
          <Tile
            label="확정 비용 (USD)"
            value={formatUsd(detail.confirmed_cost_usd, "summary")}
          />
          <Tile
            label={
              <>
                추정 비용 (USD)
                {hasEstimate && <Badge tone="blue">추정</Badge>}
              </>
            }
            value={hasEstimate ? `≈ ${estimated}` : estimated}
            tone={hasEstimate ? "estimated" : "plain"}
          />
          <Tile
            label="비용 미확인"
            value={`${formatCount(detail.unknown_cost_count)}건`}
            tone={detail.unknown_cost_count > 0 ? "warning" : "plain"}
          />
        </div>
        <p className="text-caption text-grey-600 tabular-nums">
          {facts.filter(Boolean).join(" · ")}
        </p>
      </section>
    </>
  );
}

function Tile({
  label,
  value,
  tone = "plain",
}: {
  label: ReactNode;
  value: string;
  tone?: keyof typeof TILE_CLASS;
}) {
  return (
    <div
      className={`flex flex-col gap-1 rounded-xl p-3 ${TILE_CLASS[tone].box}`}
    >
      <span className="flex items-center gap-1 text-caption text-grey-600">
        {label}
      </span>
      <span className={`font-bold tabular-nums ${TILE_CLASS[tone].value}`}>
        {value}
      </span>
    </div>
  );
}
