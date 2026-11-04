import { useEffect, useId, useState } from "react";
import { Controller, useFormContext, useWatch } from "react-hook-form";
import { Button } from "../../../shared/components/ui/Button";
import type { SimulatorDraft, SimulatorFormValues } from "../lib/form";
import { comparisonModeLabel, type ModelChoice } from "../lib/presentation";
import { TuningParameterField } from "./TuningParameterField";

export function ComparisonSettings({
  index,
  choice,
}: {
  index: number;
  choice?: ModelChoice;
}) {
  const panelId = useId();
  const {
    control,
    setValue,
    setFocus,
    formState: { errors },
  } = useFormContext<SimulatorFormValues, unknown, SimulatorDraft>();
  const mode = useWatch({
    control,
    name: `comparisons.${index}.settings.mode`,
  });
  const commonEnabled = useWatch({ control, name: "commonEnabled" }) === true;
  const [open, setOpen] = useState(mode === "custom");
  const settingsErrors = errors.comparisons?.[index]?.settings;
  const parameters = choice?.tuningParameters ?? [];
  useEffect(() => {
    if (settingsErrors) setOpen(true);
  }, [settingsErrors]);
  useEffect(() => {
    if (!open || !settingsErrors) return;
    const key = (["temperature", "maxTokens", "reasoningEffort"] as const).find(
      (name) => settingsErrors[name],
    );
    if (key) setFocus(`comparisons.${index}.settings.${key}`);
  }, [open, settingsErrors, index, setFocus]);
  const reset = () => {
    setValue(
      `comparisons.${index}.settings`,
      { mode: "shared", temperature: "", maxTokens: "", reasoningEffort: "" },
      { shouldDirty: true, shouldValidate: !!settingsErrors },
    );
  };
  return (
    <div className="mt-3 border-t border-grey-100 pt-3">
      <button
        type="button"
        aria-label={`비교 항목 ${index + 1} 설정`}
        aria-expanded={open}
        aria-controls={panelId}
        onClick={() => setOpen(!open)}
        className="flex w-full items-center gap-2 rounded-lg text-left text-label font-semibold focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand"
      >
        <span aria-hidden="true">{open ? "▾" : "▸"}</span>모델별 설정
        <span className="ml-auto font-normal text-grey-600">
          {comparisonModeLabel(mode, commonEnabled)}
        </span>
      </button>
      <div id={panelId} hidden={!open}>
        <fieldset aria-label={`비교 항목 ${index + 1} 설정`} className="mt-3">
          <label
            htmlFor={`${panelId}-custom`}
            className="flex items-center gap-2 text-body-sm"
          >
            <Controller
              control={control}
              name={`comparisons.${index}.settings.mode`}
              render={({ field }) => (
                <input
                  id={`${panelId}-custom`}
                  ref={field.ref}
                  name={field.name}
                  type="checkbox"
                  checked={field.value === "custom"}
                  disabled={!parameters.length}
                  onBlur={field.onBlur}
                  onChange={(event) => {
                    field.onChange(event.target.checked ? "custom" : "shared");
                    // 모델별 설정과 공통 설정은 함께 쓰지 않는다. 해제해도 공통 설정을 다시 켜지는 않는다.
                    if (event.target.checked)
                      setValue("commonEnabled", false, { shouldDirty: true });
                  }}
                  className="size-4 accent-brand focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand"
                />
              )}
            />
            모델별 설정 사용
          </label>
          <p className="mt-2 text-caption text-grey-600">
            {parameters.length
              ? "모델별 설정을 쓰면 공통 설정은 꺼져요. 비워 둔 항목은 기본값으로 실행해요."
              : "모델별 설정 지원 정보를 확인할 수 없어요. ‘공통 설정’에서 값을 정하거나 모델을 다시 골라 주세요."}
          </p>
          {mode === "custom" && parameters.length > 0 && (
            <div className="mt-3 flex flex-col gap-3">
              {parameters.map((parameter) => (
                <TuningParameterField
                  key={parameter.key}
                  index={index}
                  parameter={parameter}
                />
              ))}
            </div>
          )}
          {mode === "custom" && (
            <Button
              size="sm"
              variant="secondary"
              className="mt-3"
              onClick={reset}
            >
              공통 설정으로
            </Button>
          )}
        </fieldset>
      </div>
    </div>
  );
}
