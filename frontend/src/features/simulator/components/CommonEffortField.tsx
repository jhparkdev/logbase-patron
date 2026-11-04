import { useId } from "react";
import { Controller, useFormContext } from "react-hook-form";
import { commonEffortOptions } from "../lib/common-parameters";
import type { SimulatorDraft, SimulatorFormValues } from "../lib/form";
import { controlClass } from "../lib/limits";
import type { ModelChoice } from "../lib/presentation";
import { FieldError } from "./InputFields";

export function CommonEffortField({ choices }: { choices: ModelChoice[] }) {
  const id = useId();
  const {
    control,
    formState: { errors },
  } = useFormContext<SimulatorFormValues, unknown, SimulatorDraft>();
  const options = commonEffortOptions(choices);
  return (
    <div>
      <label htmlFor={id} className="mb-2 block text-label font-semibold">
        공통 추론 강도 (effort)
      </label>
      <Controller
        control={control}
        name="reasoningEffort"
        render={({ field }) => (
          <select
            {...field}
            id={id}
            className={controlClass}
            disabled={!options.length && !field.value}
            aria-invalid={!!errors.reasoningEffort}
            aria-describedby={`${id}-help ${id}-error`}
          >
            <option value="">기본값 사용</option>
            {field.value &&
              !options.some((option) => option.value === field.value) && (
                <option value={field.value} disabled>
                  현재 지원 정보를 확인할 수 없는 값
                </option>
              )}
            {options.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        )}
      />
      <p id={`${id}-help`} className="mt-2 text-caption text-grey-600">
        {options.length
          ? "카탈로그에서 지원이 확인된 선택지예요. 모델별 값이 우선이고, 적용될 설정을 지원하지 않거나 지원 정보를 확인할 수 없는 모델이 있으면 실행을 막아요."
          : "추론 강도의 지원 선택지를 확인할 수 없어요. 지원 정보가 있는 모델이 필요해요. 저장된 값은 기본값 사용으로 해제할 수 있어요."}
      </p>
      <FieldError
        id={`${id}-error`}
        message={errors.reasoningEffort?.message}
      />
    </div>
  );
}
