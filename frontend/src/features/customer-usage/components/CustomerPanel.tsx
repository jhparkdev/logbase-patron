import { useQuery } from "@tanstack/react-query";
import { ApiError } from "../../../shared/api/client";
import type { components } from "../../../shared/api/schema";
import { BudgetForm } from "../../../shared/components/budget/BudgetForm";
import { Badge } from "../../../shared/components/ui/Badge";
import { Button } from "../../../shared/components/ui/Button";
import { Result } from "../../../shared/components/ui/Result";
import { SidePanel } from "../../../shared/components/ui/SidePanel";
import { Skeleton } from "../../../shared/components/ui/Skeleton";
import { TextLink } from "../../../shared/components/ui/TextLink";
import { UsageBar } from "../../../shared/components/ui/UsageBar";
import {
  amountForInput,
  budgetStatusBadge,
  usageView,
} from "../../../shared/lib/budget";
import {
  formatCount,
  formatUsd,
  isZeroAmount,
  unreflectedText,
} from "../../../shared/lib/format";
import { customerDetailQuery } from "../api/usage";
import { useSaveCustomerBudget } from "../hooks/useSaveCustomerBudget";

const SAVE_FAILED_MESSAGE = "예산을 저장하지 못했어요. 다시 시도해 주세요.";

type Detail = components["schemas"]["CustomerUsageDetail"];

type CustomerPanelProps = {
  customerId: number;
  /** 예산을 비교하는 달 "YYYY-MM" */
  budgetMonth: string;
  onClose: () => void;
};

/** 고객 상세 패널. 제목은 고객명이고, 불러오는 동안에는 "고객 상세"로 둔다. */
export function CustomerPanel({
  customerId,
  budgetMonth,
  onClose,
}: CustomerPanelProps) {
  const detail = useQuery(customerDetailQuery(customerId, budgetMonth));
  return (
    <SidePanel
      title={detail.data?.customer_name ?? "고객 상세"}
      onClose={onClose}
    >
      {detail.isPending && <PanelSkeleton budgetMonth={budgetMonth} />}
      {detail.isError && (
        <Result
          title="고객 상세를 불러오지 못했어요"
          description="잠시 후 다시 시도해 주세요."
          action={
            <Button
              variant="secondary"
              size="sm"
              onClick={() => detail.refetch()}
            >
              다시 시도
            </Button>
          }
        />
      )}
      {detail.data && (
        <PanelContent
          customerId={customerId}
          budgetMonth={budgetMonth}
          detail={detail.data}
          onClose={onClose}
        />
      )}
    </SidePanel>
  );
}

function PanelSkeleton({ budgetMonth }: { budgetMonth: string }) {
  return (
    <section className="flex flex-col gap-3">
      <h3 className="font-bold">{budgetMonth} 사용 요약</h3>
      <Skeleton className="h-20" />
    </section>
  );
}

function PanelContent({
  customerId,
  budgetMonth,
  detail,
  onClose,
}: {
  customerId: number;
  budgetMonth: string;
  detail: Detail;
  onClose: () => void;
}) {
  const save = useSaveCustomerBudget(customerId);
  const budget = detail.budget;
  const badge = budgetStatusBadge(budget.status);
  const estimated = formatUsd(detail.estimated_cost_usd, "summary");
  const unreflected = unreflectedText(detail.unknown_cost_count);
  const defaultAmount = amountForInput(budget.monthly_amount_usd);
  return (
    <div className="flex flex-col gap-8">
      <section className="flex flex-col gap-3">
        <h3 className="flex items-baseline gap-2 font-bold">
          {budgetMonth} 사용 요약
          <span className="text-label font-normal text-grey-600">
            전체 서비스 합계
          </span>
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
          <div className="flex flex-col gap-1 rounded-xl bg-grey-50 p-3">
            <span className="text-caption text-grey-600">
              예산 사용률 (추정 포함)
            </span>
            <Badge tone={badge.tone}>{badge.label}</Badge>
          </div>
        </div>
        <UsageBar usage={usageView(budget)} />
        {unreflected && (
          <p className="text-caption text-grey-600">{unreflected}</p>
        )}
      </section>
      <ServiceUsageTable services={detail.services} />
      <TextLink
        from="/customer-usage"
        to="/customer-usage"
        search={(prev) => ({
          ...prev,
          customer: customerId,
          detail: undefined,
          page: undefined,
        })}
        className="self-start text-body-sm"
      >
        이 고객 사용 내역 보기 ›
      </TextLink>
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
          key={`${budgetMonth}-${defaultAmount}`}
          defaultMonth={budgetMonth}
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

/** 서비스별 예산이 아니라, 고객 예산에서 그 서비스가 차지하는 비중을 보여 준다. */
function ServiceUsageTable({ services }: { services: Detail["services"] }) {
  if (services.length === 0) {
    return null;
  }
  return (
    <section className="flex flex-col gap-3">
      <h3 className="font-bold">서비스별 사용액</h3>
      <table className="w-full text-label tabular-nums">
        <thead className="text-grey-600">
          <tr>
            <th scope="col" className="py-1.5 text-left font-medium">
              서비스
            </th>
            <th scope="col" className="py-1.5 text-right font-medium">
              확정 (USD)
            </th>
            <th scope="col" className="py-1.5 text-right font-medium">
              추정 (USD)
            </th>
            <th scope="col" className="py-1.5 text-right font-medium">
              미확인
            </th>
            <th scope="col" className="py-1.5 text-right font-medium">
              예산 비중
            </th>
          </tr>
        </thead>
        <tbody>
          {services.map((service) => (
            <tr key={service.service_id} className="border-t border-grey-100">
              <td className="py-2">{service.service_name}</td>
              <td className="py-2 text-right">
                {formatUsd(service.confirmed_cost_usd, "summary")}
              </td>
              <td className="py-2 text-right">
                {isZeroAmount(service.estimated_cost_usd) ? "" : "≈ "}
                {formatUsd(service.estimated_cost_usd, "summary")}
              </td>
              <td className="py-2 text-right">
                {formatCount(service.unknown_cost_count)}건
              </td>
              <td className="py-2 text-right">
                {service.budget_share_pct === null
                  ? "미설정"
                  : `${Math.round(Number(service.budget_share_pct))}%`}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
