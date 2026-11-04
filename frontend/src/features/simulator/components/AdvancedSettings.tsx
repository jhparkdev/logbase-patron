import { useEffect, useId } from "react";
import { Controller, useFormContext, useWatch } from "react-hook-form";
import { Button } from "../../../shared/components/ui/Button";
import { hasCustomComparison } from "../lib/comparisons";
import type { SimulatorDraft, SimulatorFormValues } from "../lib/form";
import { controlClass, TEMPERATURE } from "../lib/limits";
import {
  commonSettingsNote,
  type ModelChoice,
  type ScenarioChoice,
} from "../lib/presentation";
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
    clearErrors,
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
  const commonEnabled = useWatch({ control, name: "commonEnabled" }) === true;
  const comparisons = useWatch({ control, name: "comparisons" });
  const locked = hasCustomComparison(comparisons);
  const reset = () => {
    resetField("temperature", { defaultValue: "" });
    resetField("maxTokens", { defaultValue: "" });
    resetField("reasoningEffort", { defaultValue: "" });
  };
  return (
    <section className="rounded-xl border border-grey-200 px-4 py-3">
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
        비교할 모든 모델에 함께 쓸 Temperature, 최대 출력 토큰, 추론
        강도(effort)를 정해요. 모델별 설정을 쓰는 비교 항목이 있으면 공통 설정은
        꺼져요.
      </p>
      <div id={panelId} hidden={!open} className="pt-4">
        <label
          htmlFor={`${panelId}-enabled`}
          className="flex items-center gap-2 text-body-sm font-semibold has-disabled:text-grey-400"
        >
          <Controller
            control={control}
            name="commonEnabled"
            render={({ field }) => (
              <input
                id={`${panelId}-enabled`}
                ref={field.ref}
                name={field.name}
                type="checkbox"
                checked={field.value === true}
                disabled={locked}
                onBlur={field.onBlur}
                onChange={(event) => {
                  field.onChange(event.target.checked);
                  // 꺼진 공통값은 검사하지 않으므로 남아 있던 오류 문구도 지운다.
                  if (!event.target.checked)
                    clearErrors([
                      "temperature",
                      "maxTokens",
                      "reasoningEffort",
                    ]);
                }}
                aria-describedby={`${panelId}-state`}
                className="size-4 accent-brand focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand"
              />
            )}
          />
          공통 설정 사용
        </label>
        <p id={`${panelId}-state`} className="mt-2 text-caption text-grey-600">
          {commonSettingsNote(commonEnabled, locked)}
        </p>
        {scenario && (
          <p className="mt-1 text-caption text-grey-600">
            시나리오 기본 설정: Temperature{" "}
            {scenario.defaults.temperature ?? "모델 기본값"} · 최대 출력 토큰{" "}
            {scenario.defaults.maxTokens ?? "모델 기본값"}
            {commonEnabled ? "" : " · 공통 설정을 켜면 적용돼요"}
          </p>
        )}
        <fieldset
          disabled={!commonEnabled}
          aria-label="공통 설정 값"
          className="mt-4 min-w-0 disabled:opacity-60"
        >
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
                비워 두면 기본값을 써요. 낮을수록 답이 일정해요.
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
                비워 두면 기본값을 써요. 모델마다 허용량이 달라요.
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
        </fieldset>
        <div className="mt-3 flex items-center justify-between">
          <p className="text-caption text-grey-600">
            Provider는 고정하고 자동 대체는 쓰지 않아요.
          </p>
          <Button size="sm" variant="secondary" onClick={reset}>
            기본 설정으로
          </Button>
        </div>
      </div>
    </section>
  );
}
