import { zodResolver } from "@hookform/resolvers/zod";
import { Controller, useForm } from "react-hook-form";
import {
  FIELD_INPUT_CLASS,
  FIELD_TEXTAREA_CLASS,
  FormActions,
  FormField,
  FormHint,
} from "../../../shared/components/ui/PanelForm";
import { Select } from "../../../shared/components/ui/Select";
import type { SubscriptionProject } from "../api/budget";
import {
  emptySubscription,
  type SubscriptionFormInput,
  type SubscriptionFormValues,
  subscriptionCreateSchema,
  subscriptionFormSchema,
} from "../lib/forms";
import { SubscriptionFixedFields } from "./SubscriptionFixedFields";
import { SubscriptionNewFields } from "./SubscriptionNewFields";
import { SubscriptionStatusField } from "./SubscriptionStatusField";

/** 아직 프로젝트를 고르지 않은 상태를 보여 주는 안내 항목. 고르면 제출되지 않는다. */
const PLACEHOLDER_OPTION = { value: "", label: "프로젝트를 골라 주세요" };

/** 등록·수정이 함께 받는 props. 패널이 저장 상태와 선택지를 채운다. */
export type SubscriptionFormCommonProps = {
  /** 선택지를 아직 못 받았으면 프로젝트 상자만 비활성이다. */
  projects?: SubscriptionProject[];
  /** 저장하는 동안 제출 버튼을 막아 같은 요청이 두 번 가지 않게 한다. */
  submitting?: boolean;
  /** 서버가 거절한 이유. 폼 위에 보여 준다. */
  errorMessage?: string;
  onSubmit: (values: SubscriptionFormValues) => void;
  onClose: () => void;
};

type SubscriptionFormProps = SubscriptionFormCommonProps &
  (
    | {
        /** 등록. 적용 월의 처음 값 "YYYY-MM" */
        defaultMonth: string;
        editing?: never;
      }
    | {
        /** 수정. 구독 식별값·도구명·구독 종류·적용 월은 글자로만 보여 준다. */
        editing: SubscriptionFormValues;
        defaultMonth?: never;
      }
  );

/**
 * 구독료 등록·수정 폼. 제출할 때만 검증한다. 상태는 수정에서만 바꾼다.
 * 등록은 귀속 프로젝트를 반드시 골라야 한다. 수정은 프로젝트를 비울 수 없고,
 * 옛 미배분 구독료(프로젝트가 비어 있음)만 그대로 두고 다른 칸을 저장할 수 있다.
 */
export function SubscriptionForm({
  projects,
  submitting = false,
  errorMessage,
  onSubmit,
  onClose,
  defaultMonth,
  editing,
}: SubscriptionFormProps) {
  const {
    control,
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<SubscriptionFormInput, unknown, SubscriptionFormValues>({
    defaultValues: editing ?? emptySubscription(defaultMonth),
    resolver: zodResolver(
      editing ? subscriptionFormSchema : subscriptionCreateSchema,
    ),
    reValidateMode: "onSubmit",
  });

  // 프로젝트가 이미 있는 구독료는 비울 수 없으므로 안내 항목을 두지 않는다
  const withPlaceholder = editing === undefined || editing.project === "";

  return (
    <form
      noValidate
      onSubmit={handleSubmit((values) => onSubmit(values))}
      className="flex flex-col gap-4"
    >
      {errorMessage && (
        <p
          role="alert"
          className="rounded-xl bg-danger-weak p-3 text-label font-medium text-red-600"
        >
          {errorMessage}
        </p>
      )}
      {editing ? (
        <SubscriptionFixedFields values={editing} />
      ) : (
        <SubscriptionNewFields register={register} errors={errors} />
      )}
      <FormField label="금액 (USD)" error={errors.amount?.message}>
        {(field) => (
          <input
            inputMode="decimal"
            className={`${FIELD_INPUT_CLASS} text-right tabular-nums`}
            {...field}
            {...register("amount")}
          />
        )}
      </FormField>
      <Controller
        control={control}
        name="project"
        render={({ field, fieldState }) => (
          <div className="flex flex-col gap-1.5">
            <Select
              label="귀속 프로젝트"
              labelPosition="top"
              value={field.value}
              options={[
                ...(withPlaceholder ? [PLACEHOLDER_OPTION] : []),
                ...(projects ?? []).map((project) => ({
                  value: String(project.project_id),
                  label: project.name,
                })),
              ]}
              onChange={field.onChange}
              disabled={projects === undefined}
              className="w-full"
            />
            {fieldState.error && (
              <p className="text-label font-medium text-red-600">
                {fieldState.error.message}
              </p>
            )}
          </div>
        )}
      />
      {editing && <SubscriptionStatusField field={register("status")} />}
      <FormField label="메모 (선택)">
        {(field) => (
          <textarea
            rows={3}
            className={FIELD_TEXTAREA_CLASS}
            {...field}
            {...register("note")}
          />
        )}
      </FormField>
      <FormHint>
        결제 후 실제로 청구된 금액을 USD로 적어 주세요. 구독 식별값은 같은
        구독을 매달 묶는 값이라 매달 같은 값으로 등록하고(예:
        command-code-team), 한 달에 한 번만 등록할 수 있어요. 구독
        식별값·도구명·구독 종류·적용 월은 등록 뒤에 바꿀 수 없어요.
      </FormHint>
      <FormActions
        submitLabel={editing ? "저장" : "등록"}
        canSubmit={!submitting}
        onClose={onClose}
      />
    </form>
  );
}
