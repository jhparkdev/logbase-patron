import { useMutation, useQueryClient } from "@tanstack/react-query";
import type { BudgetFormValues } from "../../../shared/lib/budget";
import { PROJECT_BUDGET_AFFECTED_KEYS, saveProjectBudget } from "../api/budget";

/** 프로젝트 예산 저장. 성공하면 예산을 보여 주는 프로젝트 표와 상세만 다시 불러온다. */
export function useSaveProjectBudget(projectId: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (values: BudgetFormValues) =>
      saveProjectBudget(projectId, {
        monthly_amount_usd: values.amount,
        effective_from_month: values.effectiveFrom,
      }),
    onSuccess: () =>
      Promise.all(
        PROJECT_BUDGET_AFFECTED_KEYS.map((queryKey) =>
          queryClient.invalidateQueries({ queryKey }),
        ),
      ),
  });
}
