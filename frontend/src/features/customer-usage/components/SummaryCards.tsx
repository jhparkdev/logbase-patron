import { useSuspenseQuery } from "@tanstack/react-query";
import warningIcon from "../../../assets/warning.svg";
import { StatCard } from "../../../shared/components/ui/StatCard";
import { formatCount, formatUsd } from "../../../shared/lib/format";
import { usageSummaryQuery } from "../api/usage";
import type { CustomerUsageSearch } from "../lib/search";
import { isZeroAmount, summaryTrend } from "../lib/view";

const TREND_LABEL = "이전 기간 대비";

/** 요약 카드 5개. 앞의 4개 아이콘은 파일을 받으면 icon으로 넘긴다. */
export function SummaryCards({ search }: { search: CustomerUsageSearch }) {
  const { data } = useSuspenseQuery(usageSummaryQuery(search));
  const estimated = formatUsd(data.estimated_cost_usd, "summary");
  return (
    <div className="grid grid-cols-5 gap-4">
      <StatCard
        label="작업 건수"
        value={formatCount(data.task_count)}
        trend={summaryTrend(data.task_change_pct)}
        trendLabel={TREND_LABEL}
      />
      <StatCard
        label="API 호출 수"
        value={formatCount(data.call_count)}
        trend={summaryTrend(data.call_change_pct)}
        trendLabel={TREND_LABEL}
      />
      <StatCard
        label="확정 API 비용"
        value={formatUsd(data.confirmed_cost_usd, "summary")}
        unit="USD"
        trend={summaryTrend(data.confirmed_cost_change_pct)}
        trendLabel={TREND_LABEL}
      />
      <StatCard
        label="추정 API 비용"
        value={
          // 좁은 카드에서 ≈만 윗줄에 남지 않게 줄바꿈 없는 공백으로 잇는다.
          isZeroAmount(data.estimated_cost_usd) ? estimated : `≈ ${estimated}`
        }
        unit="USD"
        trend={summaryTrend(data.estimated_cost_change_pct)}
        trendLabel={TREND_LABEL}
      />
      <StatCard
        label="비용 미확인 건수"
        value={formatCount(data.unknown_cost_count)}
        unit="건"
        icon={warningIcon}
        warning={data.unknown_cost_count > 0}
        caption={
          data.unknown_cost_count > 0 ? "위 금액에 넣지 않았어요" : undefined
        }
      />
    </div>
  );
}
