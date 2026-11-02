import type { FieldErrors, UseFormRegister } from "react-hook-form";
import {
  FIELD_INPUT_CLASS,
  FormField,
} from "../../../shared/components/ui/PanelForm";
import type { SubscriptionFormInput } from "../lib/forms";

type SubscriptionNewFieldsProps = {
  register: UseFormRegister<SubscriptionFormInput>;
  errors: FieldErrors<SubscriptionFormInput>;
};

/** 등록할 때만 입력하는 칸. 등록 뒤에는 바꿀 수 없어 수정 폼에서는 글자로만 보여 준다. */
export function SubscriptionNewFields({
  register,
  errors,
}: SubscriptionNewFieldsProps) {
  return (
    <>
      <FormField label="구독 식별값" error={errors.reference?.message}>
        {(field) => (
          <input
            className={FIELD_INPUT_CLASS}
            {...field}
            {...register("reference")}
          />
        )}
      </FormField>
      <div className="grid grid-cols-2 gap-3">
        <FormField label="도구명" error={errors.toolName?.message}>
          {(field) => (
            <input
              className={FIELD_INPUT_CLASS}
              {...field}
              {...register("toolName")}
            />
          )}
        </FormField>
        <FormField label="구독 종류 (선택)">
          {(field) => (
            <input
              className={FIELD_INPUT_CLASS}
              {...field}
              {...register("type")}
            />
          )}
        </FormField>
      </div>
      <FormField label="적용 월" error={errors.month?.message}>
        {(field) => (
          <input
            type="month"
            className={FIELD_INPUT_CLASS}
            {...field}
            {...register("month")}
          />
        )}
      </FormField>
    </>
  );
}
