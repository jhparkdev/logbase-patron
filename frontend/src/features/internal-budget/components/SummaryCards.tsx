import { useSuspenseQuery } from "@tanstack/react-query";
import calendarIcon from "../../../assets/calendar.svg";
import costIcon from "../../../assets/cost.svg";
import estimatedCostIcon from "../../../assets/estimatedCost.svg";
import managedCostIcon from "../../../assets/managedCost.svg";
import { StatCard } from "../../../shared/components/ui/StatCard";
import { formatUsd, isZeroAmount } from "../../../shared/lib/format";
import { internalSummaryQuery } from "../api/budget";
import type { BudgetFilter } from "../lib/search";
import {
  managedTotalCaption,
  SUMMARY_LABELS,
  subscriptionCaption,
} from "../lib/summary";

/** 비용 요약 카드 4개. 합계는 서버가 계산한 값을 그대로 보여 준다. */
export function SummaryCards({ filter }: { filter: BudgetFilter }) {
  const { data } = useSuspenseQuery(internalSummaryQuery(filter));
  const estimated = formatUsd(data.api_estimated_usd, "summary");
  return (
    <div className="grid grid-cols-4 gap-4">
      <StatCard
        label={SUMMARY_LABELS.confirmed}
        value={formatUsd(data.api_confirmed_usd, "summary")}
        unit="USD"
        icon={costIcon}
        iconTone="green"
        caption="실제 사용 기준"
      />
      <StatCard
        label={SUMMARY_LABELS.estimated}
        value={
          // 좁은 카드에서 ≈만 윗줄에 남지 않게 줄바꿈 없는 공백으로 잇는다.
          isZeroAmount(data.api_estimated_usd) ? estimated : `≈ ${estimated}`
        }
        unit="USD"
        icon={estimatedCostIcon}
        iconTone="blue"
        caption="진행 중 사용량 기반 추정"
      />
      <StatCard
        label={SUMMARY_LABELS.subscription}
        value={formatUsd(data.subscription_usd, "summary")}
        unit="USD"
        icon={calendarIcon}
        iconTone="blue"
        caption={subscriptionCaption(data.subscription_excluded)}
      />
      <StatCard
        label={SUMMARY_LABELS.total}
        value={formatUsd(data.total_managed_usd, "summary")}
        unit="USD"
        icon={managedCostIcon}
        iconTone="blue"
        caption={managedTotalCaption(
          data.unknown_cost_count,
          data.subscription_excluded,
        )}
      />
    </div>
  );
}
