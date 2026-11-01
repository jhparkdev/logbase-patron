import { useEffect, useId } from "react";
import { Controller, useFormContext, useWatch } from "react-hook-form";
import { Button } from "../../../shared/components/ui/Button";
import type { SimulatorDraft, SimulatorFormValues } from "../lib/form";
import { controlClass, TEMPERATURE } from "../lib/limits";
import type { ModelChoice, ScenarioChoice } from "../lib/presentation";
import { CommonEffortField } from "./CommonEffortField";

export function AdvancedSettings({
  open,
  onToggle,
  scenario,
  choices,
}: {
  open: boolean;
  onToggle: () => void;
  scenario?: ScenarioChoice;
  choices: ModelChoice[];
}) {
  const panelId = useId();
  const {
    control,
    register,
    resetField,
    setFocus,
    formState: { errors },
  } = useFormContext<SimulatorFormValues, unknown, SimulatorDraft>();
  useEffect(() => {
    if (!open) return;
    if (errors.temperature) setFocus("temperature");
    else if (errors.maxTokens) setFocus("maxTokens");
    else if (errors.reasoningEffort) setFocus("reasoningEffort");
  }, [
    open,
    errors.temperature,
    errors.maxTokens,
    errors.reasoningEffort,
    setFocus,
  ]);
  const temperature = useWatch({ control, name: "temperature" });
  const reset = () => {
    resetField("temperature", { defaultValue: "" });
    resetField("maxTokens", { defaultValue: "" });
    resetField("reasoningEffort", { defaultValue: "" });
  };
  return (
    <section className="border-t border-grey-100 py-4">
      <button
        type="button"
        onClick={onToggle}
        aria-expanded={open}
        aria-controls={panelId}
        aria-describedby={`${panelId}-help`}
        className="flex w-full items-center gap-2 rounded-lg py-1 text-left text-body-sm font-semibold focus-visible:outline-2 focus-visible:outline-brand"
      >
        <span aria-hidden="true">{open ? "▾" : "▸"}</span>공통 설정{" "}
        <span className="ml-auto text-label font-normal text-grey-600">
          선택사항
        </span>
      </button>
      <p id={`${panelId}-help`} className="mt-2 text-caption text-grey-600">
        비교할 모든 모델에 함께 사용할 Temperature, 최대 출력 토큰, 추론
        강도(effort)를 지정합니다. 모델별로 값을 지정한 항목에는 모델별 설정이
        우선 적용됩니다.
      </p>
      <div id={panelId} hidden={!open} className="pt-4">
        <p className="mb-4 text-caption text-grey-600">
          공통값을 비워 두면 선택한 시나리오의 기본값을 사용합니다. 시나리오
          기본값도 없으면 모델 기본값을 사용합니다.
        </p>
        <div className="grid grid-cols-2 gap-6">
          <div>
            <label
              htmlFor="sim-temperature"
              className="mb-2 block text-label font-semibold"
            >
              공통 Temperature
            </label>
            <Controller
              name="temperature"
              control={control}
              render={({ field }) => (
                <>
                  <input
                    {...field}
                    id="sim-temperature"
                    type="number"
                    min={TEMPERATURE.min}
                    max={TEMPERATURE.max}
                    step={TEMPERATURE.step}
                    placeholder="기본값 사용"
                    aria-invalid={!!errors.temperature}
                    aria-describedby="sim-temperature-help sim-temperature-error"
                    className={controlClass}
                  />
                  <input
                    type="range"
                    aria-label="공통 Temperature 조절"
                    aria-valuetext={
                      temperature.trim() === ""
                        ? "기본값 사용. 조절하면 직접 지정합니다."
                        : temperature
                    }
                    min={TEMPERATURE.min}
                    max={TEMPERATURE.max}
                    step={TEMPERATURE.step}
                    value={
                      temperature.trim() === "" ||
                      !Number.isFinite(Number(temperature))
                        ? TEMPERATURE.sliderStart
                        : Number(temperature)
                    }
                    onChange={(event) => field.onChange(event.target.value)}
                    className="mt-3 w-full accent-brand"
                  />
                </>
              )}
            />
            <p
              id="sim-temperature-help"
              className="mt-1 text-caption text-grey-600"
            >
              비워두면 기본값을 사용합니다. 낮을수록 일관된 답변을 생성합니다.
            </p>
            <p
              id="sim-temperature-error"
              role={errors.temperature ? "alert" : undefined}
              className="mt-1 text-caption text-red-600"
            >
              {errors.temperature?.message}
            </p>
          </div>
          <div>
            <label
              htmlFor="sim-max-tokens"
              className="mb-2 block text-label font-semibold"
            >
              공통 최대 출력 토큰
            </label>
            <input
              {...register("maxTokens")}
              id="sim-max-tokens"
              type="number"
              min="1"
              step="1"
              placeholder="기본값 사용"
              aria-invalid={!!errors.maxTokens}
              aria-describedby="sim-max-tokens-help sim-max-tokens-error"
              className={controlClass}
            />
            <p
              id="sim-max-tokens-help"
              className="mt-2 text-caption text-grey-600"
            >
              비워두면 기본값을 사용합니다. 모델에 따라 허용량이 다릅니다.
            </p>
            <p
              id="sim-max-tokens-error"
              role={errors.maxTokens ? "alert" : undefined}
              className="mt-1 text-caption text-red-600"
            >
              {errors.maxTokens?.message}
            </p>
          </div>
        </div>
        <div className="mt-4">
          <CommonEffortField choices={choices} />
        </div>
        {scenario && (
          <p className="mt-3 text-caption text-grey-600">
            시나리오 기본 설정: Temperature{" "}
            {scenario.defaults.temperature ?? "모델 기본값"} · 최대 출력 토큰{" "}
            {scenario.defaults.maxTokens ?? "모델 기본값"}
          </p>
        )}
        <div className="mt-3 flex items-center justify-between">
          <p className="text-caption text-grey-600">
            Provider는 고정하고 자동 대체는 사용하지 않습니다.
          </p>
          <Button size="sm" variant="secondary" onClick={reset}>
            기본 설정으로
          </Button>
        </div>
      </div>
    </section>
  );
}
