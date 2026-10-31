import { useMutation, useQueryClient } from "@tanstack/react-query";
import type { BudgetFormValues } from "../../../shared/lib/budget";
import { BUDGET_AFFECTED_KEYS, saveCustomerBudget } from "../api/usage";

/** 고객 예산 저장. 성공하면 예산을 보여 주는 표와 상세만 다시 불러온다. */
export function useSaveCustomerBudget(customerId: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (values: BudgetFormValues) =>
      saveCustomerBudget(customerId, {
        monthly_amount_usd: values.amount,
        effective_from_month: values.effectiveFrom,
      }),
    onSuccess: () =>
      Promise.all(
        BUDGET_AFFECTED_KEYS.map((queryKey) =>
          queryClient.invalidateQueries({ queryKey }),
        ),
      ),
  });
}
