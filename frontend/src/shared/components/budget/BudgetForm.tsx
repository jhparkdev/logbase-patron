import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import type { z } from "zod";
import { type BudgetFormValues, budgetFormSchema } from "../../lib/budget";
import { FIELD_INPUT_CLASS, FormActions, FormField } from "../ui/PanelForm";

type BudgetFormProps = {
  /** 적용 시작 월의 처음 값 "YYYY-MM" */
  defaultMonth: string;
  /** 월 예산의 처음 값. 없으면 빈 칸이다. */
  defaultAmount?: string;
  /** 저장하는 동안 저장 버튼을 막아 같은 요청이 두 번 가지 않게 한다. */
  submitting?: boolean;
  /** 검증을 통과한 값을 받는다. 없으면 저장할 수 없어 저장 버튼을 막는다(예산 저장 API 전). */
  onSubmit?: (values: BudgetFormValues) => void;
  onClose: () => void;
  /** 입력 전에 알아 둘 규칙. 주의 기준처럼 서버가 정하는 값은 쓰는 쪽이 받아서 넣는다 */
  hint: string;
};

/** 월 예산 입력(고객·프로젝트 공용). 저장을 누를 때만 검증한다. */
export function BudgetForm({
  defaultMonth,
  defaultAmount = "",
  submitting = false,
  onSubmit,
  onClose,
  hint,
}: BudgetFormProps) {
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<z.input<typeof budgetFormSchema>, unknown, BudgetFormValues>({
    defaultValues: { amount: defaultAmount, effectiveFrom: defaultMonth },
    resolver: zodResolver(budgetFormSchema),
    reValidateMode: "onSubmit",
  });

  return (
    <form
      noValidate
      onSubmit={handleSubmit((values) => onSubmit?.(values))}
      className="flex flex-col gap-4"
    >
      <p className="text-label text-grey-600">{hint}</p>
      <div className="grid grid-cols-2 gap-3">
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
      </div>
      <FormActions
        submitLabel="예산 저장"
        canSubmit={onSubmit !== undefined && !submitting}
        onClose={onClose}
      />
    </form>
  );
}
