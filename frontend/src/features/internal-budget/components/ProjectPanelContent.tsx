import { ApiError } from "../../../shared/api/client";
import type { components } from "../../../shared/api/schema";
import { BudgetForm } from "../../../shared/components/budget/BudgetForm";
import { Badge } from "../../../shared/components/ui/Badge";
import { amountForInput, budgetStatusBadge } from "../../../shared/lib/budget";
import {
  formatCount,
  formatUsd,
  isZeroAmount,
} from "../../../shared/lib/format";
import { useSaveProjectBudget } from "../hooks/useSaveProjectBudget";
import { projectUsageText } from "../lib/project";

const SAVE_FAILED_MESSAGE = "예산을 저장하지 못했어요. 다시 시도해 주세요.";

type ProjectPanelContentProps = {
  projectId: number;
  /** 예산을 비교하는 달 "YYYY-MM" */
  month: string;
  detail: components["schemas"]["ProjectUsageDetail"];
  onClose: () => void;
};

/** 프로젝트 상세 패널의 내용. 사용 요약과 월 예산 저장. */
export function ProjectPanelContent({
  projectId,
  month,
  detail,
  onClose,
}: ProjectPanelContentProps) {
  const save = useSaveProjectBudget(projectId);
  const badge = budgetStatusBadge(detail.budget.status);
  const estimated = formatUsd(detail.estimated_cost_usd, "summary");
  const defaultAmount = amountForInput(detail.budget.monthly_amount_usd);
  return (
    <div className="flex flex-col gap-8">
      <section className="flex flex-col gap-3">
        <h3 className="flex items-center gap-2 font-bold">
          {month} 사용 요약
          <Badge tone={badge.tone}>{badge.label}</Badge>
        </h3>
        <div className="grid grid-cols-3 gap-2">
          <SummaryValue
            label="확정 비용 (USD)"
            value={formatUsd(detail.confirmed_cost_usd, "summary")}
          />
          <SummaryValue
            label="추정 비용 (USD)"
            value={
              isZeroAmount(detail.estimated_cost_usd)
                ? estimated
                : `≈ ${estimated}`
            }
          />
          <SummaryValue
            label="비용 미확인"
            value={`${formatCount(detail.unknown_cost_count)}건`}
          />
        </div>
        <p className="text-label text-grey-700">
          {projectUsageText(detail.budget)}
        </p>
      </section>
      <section className="flex flex-col gap-3">
        <h3 className="font-bold">월 예산</h3>
        {save.isError && (
          <p
            role="alert"
            className="rounded-xl bg-danger-weak p-3 text-label font-medium text-red-600"
          >
            {save.error instanceof ApiError
              ? save.error.message
              : SAVE_FAILED_MESSAGE}
          </p>
        )}
        <BudgetForm
          // 저장한 값이 돌아오면 입력 칸도 그 값으로 다시 그린다.
          key={`${month}-${defaultAmount}`}
          defaultMonth={month}
          defaultAmount={defaultAmount}
          submitting={save.isPending}
          onSubmit={(values) => save.mutate(values)}
          onClose={onClose}
        />
      </section>
    </div>
  );
}

function SummaryValue({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex flex-col gap-1 rounded-xl bg-grey-50 p-3">
      <span className="text-caption text-grey-600">{label}</span>
      <span className="font-bold tabular-nums">{value}</span>
    </div>
  );
}
