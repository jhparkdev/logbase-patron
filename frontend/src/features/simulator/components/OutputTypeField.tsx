import { useFormContext, useWatch } from "react-hook-form";
import type { SimulatorDraft, SimulatorFormValues } from "../lib/form";
import { controlClass } from "../lib/limits";
import {
  IMAGE_COUNT_OPTIONS,
  IMAGE_QUALITY_OPTIONS,
  OUTPUT_TYPE_OPTIONS,
} from "../lib/output";
import { FieldError } from "./InputFields";

/** 결과를 텍스트로 받을지 이미지로 받을지 고른다. 이미지 옵션은 모든 칸에 같이 보낸다. */
export function OutputTypeField() {
  const {
    control,
    register,
    formState: { errors },
  } = useFormContext<SimulatorFormValues, unknown, SimulatorDraft>();
  const outputType = useWatch({ control, name: "outputType" });
  return (
    <div className="flex flex-col gap-3">
      <fieldset className="flex items-center gap-3">
        <legend className="sr-only">출력 형식</legend>
        <span aria-hidden className="text-label font-semibold">
          출력 형식
        </span>
        <div className="flex rounded-xl bg-grey-100 p-1">
          {OUTPUT_TYPE_OPTIONS.map((option) => (
            <label
              key={option.value}
              className="flex h-9 cursor-pointer items-center rounded-lg px-3.5 text-label font-semibold text-grey-600 has-checked:bg-white has-checked:text-grey-900 has-checked:shadow-sm has-focus-visible:outline-2 has-focus-visible:outline-brand"
            >
              <input
                {...register("outputType")}
                type="radio"
                value={option.value}
                className="sr-only"
              />
              {option.label}
            </label>
          ))}
        </div>
      </fieldset>
      {outputType === "IMAGE" && (
        <>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label
                htmlFor="sim-image-count"
                className="mb-2 block text-label font-semibold"
              >
                이미지 수
              </label>
              <select
                {...register("imageCount")}
                id="sim-image-count"
                aria-invalid={!!errors.imageCount}
                aria-describedby="sim-image-count-error"
                className={controlClass}
              >
                {IMAGE_COUNT_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
              <FieldError
                id="sim-image-count-error"
                message={errors.imageCount?.message}
              />
            </div>
            <div>
              <label
                htmlFor="sim-image-quality"
                className="mb-2 block text-label font-semibold"
              >
                품질
              </label>
              <select
                {...register("imageQuality")}
                id="sim-image-quality"
                aria-invalid={!!errors.imageQuality}
                aria-describedby="sim-image-quality-error"
                className={controlClass}
              >
                {IMAGE_QUALITY_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
              <FieldError
                id="sim-image-quality-error"
                message={errors.imageQuality?.message}
              />
            </div>
          </div>
          <p className="text-caption text-grey-600">
            이미지 생성에는 Temperature 같은 텍스트 설정과 JSON Schema를 보내지
            않아요.
          </p>
        </>
      )}
    </div>
  );
}
