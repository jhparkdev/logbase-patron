import { Controller, useFormContext, useWatch } from "react-hook-form";
import { Button } from "../../../shared/components/ui/Button";
import type { SimulatorDraft, SimulatorFormValues } from "../lib/form";
import { controlClass, MODEL_LIMITS } from "../lib/limits";
import type { ModelChoice } from "../lib/presentation";
import { FieldError } from "./InputFields";

export function ModelSelection({
  choices,
  unavailable,
}: {
  choices: ModelChoice[];
  unavailable: boolean;
}) {
  const {
    control,
    setValue,
    formState: { errors },
  } = useFormContext<SimulatorFormValues, unknown, SimulatorDraft>();
  const selections = useWatch({ control, name: "selections" });
  return (
    <section className="border-t border-grey-100 pt-5">
      <div className="mb-3 flex items-center justify-between">
        <h3 className="text-label font-semibold">
          모델 선택{" "}
          <span className="font-normal text-grey-600">
            ({MODEL_LIMITS.min}~{MODEL_LIMITS.max}개)
          </span>
        </h3>
        <Button
          size="sm"
          variant="secondary"
          disabled={selections.length >= MODEL_LIMITS.max}
          onClick={() => setValue("selections", [...selections, ""])}
        >
          모델 추가
        </Button>
      </div>
      <div className="grid grid-cols-2 gap-3">
        {selections.map((_, index) => {
          const selected = choices.find(
            (item) => item.key === selections[index],
          );
          // 칸 번호가 정체성이다. 모든 입력은 RHF로 제어하며 제거 후 순서대로 다시 번호를 붙인다.
          return (
            <div
              // biome-ignore lint/suspicious/noArrayIndexKey: 칸 번호가 정체성이고 내부 입력은 모두 제어된다.
              key={`slot-${index}`}
              className="rounded-control border border-grey-200 p-3"
            >
              <div className="mb-2 flex items-center justify-between">
                <label
                  htmlFor={`sim-model-${index}`}
                  className="text-label font-semibold"
                >
                  비교 모델 {index + 1}
                </label>
                <button
                  type="button"
                  aria-label={`비교 모델 ${index + 1} 제거`}
                  disabled={selections.length === 1}
                  onClick={() =>
                    setValue(
                      "selections",
                      selections.filter((_, i) => i !== index),
                      { shouldDirty: true },
                    )
                  }
                  className="rounded-lg px-2 text-caption text-grey-600 focus-visible:outline-2 focus-visible:outline-brand disabled:opacity-40"
                >
                  제거
                </button>
              </div>
              <Controller
                name={`selections.${index}`}
                control={control}
                render={({ field }) => (
                  <select
                    {...field}
                    id={`sim-model-${index}`}
                    disabled={unavailable}
                    aria-invalid={!!errors.selections?.[index]}
                    aria-describedby={`sim-model-${index}-error`}
                    className={controlClass}
                  >
                    <option value="">
                      {unavailable
                        ? "모델 목록 준비 중"
                        : "모델을 선택해 주세요"}
                    </option>
                    {choices.map((choice) => (
                      <option
                        key={choice.key}
                        value={choice.key}
                        disabled={
                          !choice.selectable ||
                          selections.some(
                            (key, i) => i !== index && key === choice.key,
                          )
                        }
                      >
                        {choice.name} · {choice.provider}
                        {!choice.selectable
                          ? ` · ${choice.unavailableReason ?? "선택 불가"}`
                          : ""}
                      </option>
                    ))}
                  </select>
                )}
              />
              {selected && (
                <p className="mt-2 text-caption text-grey-600">
                  Provider: {selected.provider} ·{" "}
                  {selected.supportsImages ? "텍스트·이미지" : "텍스트"}
                </p>
              )}
              <FieldError
                id={`sim-model-${index}-error`}
                message={errors.selections?.[index]?.message}
              />
            </div>
          );
        })}
      </div>
      <FieldError
        id="sim-selections-error"
        message={errors.selections?.root?.message ?? errors.selections?.message}
      />
    </section>
  );
}
