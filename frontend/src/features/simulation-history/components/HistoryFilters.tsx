import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { Button } from "../../../shared/components/ui/Button";
import type { HistoryOption } from "../lib/presentation";
import {
  type HistoryFilters as Filters,
  HISTORY_MAX_DAYS,
  HISTORY_STATUSES,
  historyFiltersSchema,
  STATUS_LABELS,
} from "../lib/search";
import { HistoryFilterSelect } from "./HistoryFilterSelect";

const control =
  "h-9.5 w-full rounded-control border border-neutral-weak bg-grey-50 px-3 text-body-sm focus:border-brand focus:outline-brand aria-invalid:border-red-500";
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
  const {
    register,
    control: formControl,
    handleSubmit,
    formState: { errors },
  } = useForm<Filters>({
    defaultValues: values,
    resolver: zodResolver(historyFiltersSchema),
    mode: "onSubmit",
    reValidateMode: "onSubmit",
  });
  return (
    <form
      aria-label="실행 이력 검색"
      noValidate
      onSubmit={handleSubmit(onSubmit)}
      className="rounded-2xl bg-white p-6"
    >
      <div className="grid grid-cols-2 gap-4 xl:grid-cols-5">
        <label className="text-label text-grey-600">
          조회 시작일
          <input
            type="date"
            className={control}
            aria-invalid={!!errors.from}
            aria-describedby={errors.from ? "history-from-error" : undefined}
            {...register("from")}
          />
        </label>
        <label className="text-label text-grey-600">
          조회 종료일
          <input
            type="date"
            className={control}
            aria-invalid={!!errors.to}
            aria-describedby={errors.to ? "history-to-error" : undefined}
            {...register("to")}
          />
        </label>
        {/* 시나리오 목록 API가 없는 동안에는 숨긴다. URL에 값이 있으면 지울 수 있게 남긴다 */}
        {(scenarios.length > 0 || values.scenario) && (
          <HistoryFilterSelect
            control={formControl}
            name="scenario"
            label="시나리오"
            options={scenarios}
            className={control}
          />
        )}
        <HistoryFilterSelect
          control={formControl}
          name="model"
          label="모델"
          options={models}
          className={control}
        />
        <HistoryFilterSelect
          control={formControl}
          name="status"
          label="실행 상태"
          allValue="all"
          options={HISTORY_STATUSES.filter((status) => status !== "all").map(
            (status) => ({ key: status, name: STATUS_LABELS[status] }),
          )}
          className={control}
        />
      </div>
      <div className="mt-4 flex items-end gap-4">
        <label className="grow text-label text-grey-600">
          Simulation ID
          <input
            type="text"
            placeholder="실행 ID를 입력해 주세요"
            className={control}
            aria-invalid={!!errors.simulationId}
            aria-describedby={
              errors.simulationId ? "history-id-error" : undefined
            }
            {...register("simulationId")}
          />
        </label>
        <Button type="submit">조회</Button>
      </div>
      {errors.from && (
        <p
          role="alert"
          id="history-from-error"
          className="mt-2 text-body-sm text-red-600"
        >
          {errors.from.message}
        </p>
      )}
      {errors.to && (
        <p
          role="alert"
          id="history-to-error"
          className="mt-2 text-body-sm text-red-600"
        >
          {errors.to.message}
        </p>
      )}
      {errors.simulationId && (
        <p
          role="alert"
          id="history-id-error"
          className="mt-2 text-body-sm text-red-600"
        >
          {errors.simulationId.message}
        </p>
      )}
      <p className="mt-3 text-caption text-grey-600">
        기간은 KST 기준이며 최대 {HISTORY_MAX_DAYS}일을 조회할 수 있어요.
      </p>
    </form>
  );
}
