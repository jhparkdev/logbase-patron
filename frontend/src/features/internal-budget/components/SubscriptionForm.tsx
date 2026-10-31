import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import type { z } from "zod";
import {
  type SubscriptionFormValues,
  subscriptionFormSchema,
} from "../lib/forms";
import {
  FIELD_INPUT_CLASS,
  FIELD_TEXTAREA_CLASS,
  FormActions,
  FormField,
  FormHint,
} from "./PanelForm";

const STATUS_OPTIONS = [
  { value: "active", label: "사용 중" },
  { value: "cancelled", label: "해지" },
] as const;

type SubscriptionFormProps = {
  /** 적용 월의 처음 값 "YYYY-MM" */
  defaultMonth: string;
  /** 검증을 통과한 값을 받는다. 없으면 등록할 수 없어 등록 버튼을 막는다(구독료 API 전). */
  onSubmit?: (values: SubscriptionFormValues) => void;
  onClose: () => void;
};

/**
 * 구독료 등록. 등록을 누를 때만 검증한다.
 * 귀속 프로젝트 선택은 프로젝트 목록 API가 생기면 넣는다(비우면 미배분).
 */
export function SubscriptionForm({
  defaultMonth,
  onSubmit,
  onClose,
}: SubscriptionFormProps) {
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<
    z.input<typeof subscriptionFormSchema>,
    unknown,
    SubscriptionFormValues
  >({
    defaultValues: {
      toolName: "",
      month: defaultMonth,
      amount: "",
      status: "active",
      note: "",
    },
    resolver: zodResolver(subscriptionFormSchema),
    reValidateMode: "onSubmit",
  });

  return (
    <form
      noValidate
      onSubmit={handleSubmit((values) => onSubmit?.(values))}
      className="flex flex-col gap-4"
    >
      <FormField label="도구명" error={errors.toolName?.message}>
        {(control) => (
          <input
            className={FIELD_INPUT_CLASS}
            {...control}
            {...register("toolName")}
          />
        )}
      </FormField>
      <div className="grid grid-cols-2 gap-3">
        <FormField label="적용 월" error={errors.month?.message}>
          {(control) => (
            <input
              type="month"
              className={FIELD_INPUT_CLASS}
              {...control}
              {...register("month")}
            />
          )}
        </FormField>
        <FormField label="금액 (USD)" error={errors.amount?.message}>
          {(control) => (
            <input
              inputMode="decimal"
              className={`${FIELD_INPUT_CLASS} text-right tabular-nums`}
              {...control}
              {...register("amount")}
            />
          )}
        </FormField>
      </div>
      <fieldset>
        <legend className="mb-1.5 text-label font-medium text-grey-700">
          상태
        </legend>
        <div className="grid grid-cols-2 gap-1 rounded-xl bg-grey-100 p-1">
          {STATUS_OPTIONS.map((option) => (
            <label
              key={option.value}
              className="flex h-9 cursor-pointer items-center justify-center rounded-lg text-body-sm font-medium text-grey-600 has-checked:bg-white has-checked:font-semibold has-checked:text-grey-900 has-focus-visible:outline-2 has-focus-visible:outline-brand"
            >
              <input
                type="radio"
                value={option.value}
                className="sr-only"
                {...register("status")}
              />
              {option.label}
            </label>
          ))}
        </div>
      </fieldset>
      <FormField label="메모 (선택)">
        {(control) => (
          <textarea
            rows={3}
            className={FIELD_TEXTAREA_CLASS}
            {...control}
            {...register("note")}
          />
        )}
      </FormField>
      <FormHint>
        결제 후 실제로 청구된 금액을 USD로 적어 주세요. 같은 도구는 한 달에 한
        번만 등록할 수 있어요.
      </FormHint>
      <FormActions
        submitLabel="등록"
        canSubmit={onSubmit !== undefined}
        onClose={onClose}
      />
    </form>
  );
}
