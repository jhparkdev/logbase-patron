import { zodResolver } from "@hookform/resolvers/zod";
import { useId } from "react";
import { useForm } from "react-hook-form";
import { FilterCard } from "../../../shared/components/ui/FilterCard";
import { PeriodField } from "../../../shared/components/ui/PeriodField";
import { Select } from "../../../shared/components/ui/Select";
import { type Period, periodSchema } from "../../../shared/lib/period";

/** 목록 API가 생기기 전까지 "전체"만 있고 바꿀 수 없는 선택 상자 */
const PENDING_SELECTS = [
  { label: "고객", all: "전체 고객" },
  { label: "서비스", all: "전체 서비스" },
  { label: "모델", all: "전체 모델" },
] as const;

type UsageFiltersProps = {
  period: Period;
  onSubmit: (period: Period) => void;
};

/** P-01 조회 조건. 조회 버튼을 눌러야 적용하고, 그때만 검증한다. */
export function UsageFilters({ period, onSubmit }: UsageFiltersProps) {
  const periodErrorId = useId();
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<Period>({
    defaultValues: period,
    resolver: zodResolver(periodSchema),
    reValidateMode: "onSubmit",
  });
  const periodMessage = errors.from?.message ?? errors.to?.message;
  const periodError =
    periodMessage === undefined
      ? undefined
      : { id: periodErrorId, message: periodMessage };

  return (
    <FilterCard onSubmit={handleSubmit(onSubmit)} error={periodError}>
      {PENDING_SELECTS.map((select) => (
        <Select
          key={select.label}
          label={select.label}
          showLabel
          value=""
          options={[{ value: "", label: select.all }]}
          onChange={() => {}}
          disabled
          className="w-40"
        />
      ))}
      <PeriodField
        label="기간"
        fromInput={register("from")}
        toInput={register("to")}
        errorId={periodError?.id}
      />
    </FilterCard>
  );
}
