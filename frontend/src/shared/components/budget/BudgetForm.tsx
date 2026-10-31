import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import type { z } from "zod";
import { type BudgetFormValues, budgetFormSchema } from "../../lib/budget";
import {
  FIELD_INPUT_CLASS,
  FormActions,
  FormField,
  FormHint,
} from "../ui/PanelForm";

type BudgetFormProps = {
  /** 적용 시작 월의 처음 값 "YYYY-MM" */
  defaultMonth: string;
  /** 검증을 통과한 값을 받는다. 없으면 저장할 수 없어 저장 버튼을 막는다(예산 저장 API 전). */
  onSubmit?: (values: BudgetFormValues) => void;
  onClose: () => void;
};

/** 월 예산 입력(고객·프로젝트 공용). 저장을 누를 때만 검증한다. */
export function BudgetForm({
  defaultMonth,
  onSubmit,
  onClose,
}: BudgetFormProps) {
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<z.input<typeof budgetFormSchema>, unknown, BudgetFormValues>({
    defaultValues: { amount: "", effectiveFrom: defaultMonth },
    resolver: zodResolver(budgetFormSchema),
    reValidateMode: "onSubmit",
  });

  return (
    <form
      noValidate
      onSubmit={handleSubmit((values) => onSubmit?.(values))}
      className="flex flex-col gap-4"
    >
      <FormField label="월 예산 (USD)" error={errors.amount?.message}>
        {(control) => (
          <input
            inputMode="decimal"
            className={`${FIELD_INPUT_CLASS} text-right tabular-nums`}
            {...control}
            {...register("amount")}
          />
        )}
      </FormField>
      <FormField label="적용 시작 월" error={errors.effectiveFrom?.message}>
        {(control) => (
          <input
            type="month"
            className={FIELD_INPUT_CLASS}
            {...control}
            {...register("effectiveFrom")}
          />
        )}
      </FormField>
      <FormHint>
        한 번 정하면 다음 달에도 그대로 적용돼요. 사용률이 80% 이상이면 주의,
        100% 이상이면 초과로 표시해요.
      </FormHint>
      <FormActions
        submitLabel="예산 저장"
        canSubmit={onSubmit !== undefined}
        onClose={onClose}
      />
    </form>
  );
}
