import { useQuery } from "@tanstack/react-query";
import { ApiError } from "../../../shared/api/client";
import type { components } from "../../../shared/api/schema";
import { BudgetForm } from "../../../shared/components/budget/BudgetForm";
import { Button } from "../../../shared/components/ui/Button";
import { Result } from "../../../shared/components/ui/Result";
import { SidePanel } from "../../../shared/components/ui/SidePanel";
import { Skeleton } from "../../../shared/components/ui/Skeleton";
import { TextLink } from "../../../shared/components/ui/TextLink";
import { amountForInput } from "../../../shared/lib/budget";
import { customerDetailQuery } from "../api/usage";
import { useSaveCustomerBudget } from "../hooks/useSaveCustomerBudget";
import { CustomerServiceList } from "./CustomerServiceList";
import { CustomerUsageSummary } from "./CustomerUsageSummary";

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
      {detail.isPending && <Skeleton className="h-44 rounded-2xl" />}
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
  const defaultAmount = amountForInput(detail.budget.monthly_amount_usd);
  return (
    <div className="flex flex-col gap-7">
      <CustomerUsageSummary month={budgetMonth} detail={detail} />
      <CustomerServiceList services={detail.services} />
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
      <section className="flex flex-col gap-3 rounded-2xl border border-grey-200 p-5">
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
