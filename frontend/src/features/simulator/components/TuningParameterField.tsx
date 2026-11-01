import { useId } from "react";
import { Controller, useFormContext } from "react-hook-form";
import type { SimulatorDraft, SimulatorFormValues } from "../lib/form";
import { controlClass } from "../lib/limits";
import { PARAMETER_LABELS, type TuningParameter } from "../lib/parameters";
import { FieldError } from "./InputFields";

export function TuningParameterField({
  index,
  parameter,
}: {
  index: number;
  parameter: TuningParameter;
}) {
  const id = useId();
  const {
    control,
    formState: { errors },
  } = useFormContext<SimulatorFormValues, unknown, SimulatorDraft>();
  const error = errors.comparisons?.[index]?.settings?.[parameter.key]?.message;
  return (
    <div>
      <label htmlFor={id} className="mb-1 block text-label font-semibold">
        {PARAMETER_LABELS[parameter.key]}
      </label>
      <Controller
        control={control}
        name={`comparisons.${index}.settings.${parameter.key}`}
        render={({ field }) =>
          parameter.kind === "choice" ? (
            <select
              {...field}
              id={id}
              aria-invalid={!!error}
              aria-describedby={`${id}-help ${id}-error`}
              className={controlClass}
            >
              <option value="">공통 설정 사용</option>
              {field.value &&
                !parameter.options.some(
                  (option) => option.value === field.value,
                ) && (
                  <option value={field.value} disabled>
                    현재 지원하지 않는 설정
                  </option>
                )}
              {parameter.options.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          ) : (
            <input
              {...field}
              id={id}
              type="number"
              min={parameter.min}
              max={parameter.max}
              step={parameter.step}
              placeholder="공통 설정 사용"
              aria-invalid={!!error}
              aria-describedby={`${id}-help ${id}-error`}
              className={`${controlClass} text-right tabular-nums`}
            />
          )
        }
      />
      <p id={`${id}-help`} className="mt-1 text-caption text-grey-600">
        {parameter.kind === "number"
          ? `${parameter.min}~${parameter.max}${parameter.key === "maxTokens" ? " 정수" : ""}`
          : "이 모델에 전달된 지원 선택지만 표시합니다."}
      </p>
      <FieldError id={`${id}-error`} message={error} />
    </div>
  );
}
