import { zodResolver } from "@hookform/resolvers/zod";
import { useId } from "react";
import { Controller, useForm } from "react-hook-form";
import { FilterCard } from "../../../shared/components/ui/FilterCard";
import { FIELD_CLASS } from "../../../shared/components/ui/fieldStyle";
import { PeriodField } from "../../../shared/components/ui/PeriodField";
import { Select } from "../../../shared/components/ui/Select";
import { historySelectOptions } from "../lib/filter-options";
import type { HistoryOption } from "../lib/presentation";
import {
  type HistoryFilters as Filters,
  HISTORY_MAX_DAYS,
  HISTORY_STATUSES,
  historyFiltersSchema,
  STATUS_LABELS,
} from "../lib/search";

const STATUS_OPTIONS = HISTORY_STATUSES.filter(
  (status) => status !== "all",
).map((status) => ({ key: status, name: STATUS_LABELS[status] }));

export function HistoryFilters({
  values,
  scenarios,
  models,
  onSubmit,
}: {
  values: Filters;
  scenarios: readonly HistoryOption[];
  models: readonly HistoryOption[];
  onSubmit: (value: Filters) => void;
}) {
  const periodErrorId = useId();
  const simulationIdErrorId = useId();
  const simulationIdInputId = useId();
  const {
    register,
    control,
    handleSubmit,
    formState: { errors },
  } = useForm<Filters>({
    defaultValues: values,
    resolver: zodResolver(historyFiltersSchema),
    mode: "onSubmit",
    reValidateMode: "onSubmit",
  });
  const periodMessage = errors.from?.message ?? errors.to?.message;
  const simulationIdMessage = errors.simulationId?.message;
  return (
    <FilterCard
      onSubmit={handleSubmit(onSubmit)}
      errors={[
        { id: periodErrorId, message: periodMessage },
        { id: simulationIdErrorId, message: simulationIdMessage },
      ]}
      note={`기간은 KST 기준이며 최대 ${HISTORY_MAX_DAYS}일을 조회할 수 있어요.`}
    >
      <PeriodField
        label="기간"
        fromInput={register("from")}
        toInput={register("to")}
        errorId={periodMessage && periodErrorId}
      />
      {/* 고를 시나리오가 없으면 숨긴다. URL에 값이 있으면 지울 수 있게 남긴다 */}
      {(scenarios.length > 0 || values.scenario) && (
        <Controller
          control={control}
          name="scenario"
          render={({ field }) => (
            <Select
              label="시나리오"
              labelPosition="side"
              value={field.value}
              options={historySelectOptions("시나리오", scenarios, field.value)}
              onChange={field.onChange}
              className="w-40"
            />
          )}
        />
      )}
      <Controller
        control={control}
        name="model"
        render={({ field }) => (
          <Select
            label="모델"
            labelPosition="side"
            value={field.value}
            options={historySelectOptions("모델", models, field.value)}
            onChange={field.onChange}
            className="w-40"
          />
        )}
      />
      <Controller
        control={control}
        name="status"
        render={({ field }) => (
          <Select
            label="실행 상태"
            labelPosition="side"
            value={field.value}
            options={historySelectOptions(
              "실행 상태",
              STATUS_OPTIONS,
              field.value,
              "all",
            )}
            onChange={field.onChange}
            className="w-40"
          />
        )}
      />
      <div className="flex items-center gap-2">
        <label
          htmlFor={simulationIdInputId}
          className="text-label font-medium text-grey-700"
        >
          Simulation ID
        </label>
        <input
          id={simulationIdInputId}
          type="text"
          placeholder="실행 ID를 입력해 주세요"
          className={`${FIELD_CLASS} w-80 px-3 placeholder:text-grey-500`}
          aria-invalid={simulationIdMessage !== undefined}
          aria-describedby={simulationIdMessage && simulationIdErrorId}
          {...register("simulationId")}
        />
      </div>
    </FilterCard>
  );
}
