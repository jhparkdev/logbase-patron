import { zodResolver } from "@hookform/resolvers/zod";
import { useQuery } from "@tanstack/react-query";
import { useId } from "react";
import { Controller, useForm } from "react-hook-form";
import { FilterCard } from "../../../shared/components/ui/FilterCard";
import { PeriodField } from "../../../shared/components/ui/PeriodField";
import { Select } from "../../../shared/components/ui/Select";
import { usageOptionsQuery } from "../api/usage";
import { type UsageFilterForm, usageFilterFormSchema } from "../lib/search";

/** 선택 상자 이름과 "전체" 항목, 목록 응답의 칸 */
const SELECTS = [
  { name: "customer", label: "고객", all: "전체 고객", options: "customers" },
  { name: "service", label: "서비스", all: "전체 서비스", options: "services" },
  { name: "model", label: "모델", all: "전체 모델", options: "models" },
] as const;

type UsageFiltersProps = {
  values: UsageFilterForm;
  onSubmit: (values: UsageFilterForm) => void;
};

/** P-01 조회 조건. 조회 버튼을 눌러야 적용하고, 그때만 검증한다. */
export function UsageFilters({ values, onSubmit }: UsageFiltersProps) {
  const periodErrorId = useId();
  // 목록을 못 불러와도 기간 조회는 쓸 수 있도록 화면 틀을 막지 않는다.
  const options = useQuery(usageOptionsQuery);
  const {
    control,
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<UsageFilterForm>({
    defaultValues: values,
    resolver: zodResolver(usageFilterFormSchema),
    reValidateMode: "onSubmit",
  });
  const periodMessage = errors.from?.message ?? errors.to?.message;
  return (
    <FilterCard
      onSubmit={handleSubmit(onSubmit)}
      errors={[{ id: periodErrorId, message: periodMessage }]}
    >
      {SELECTS.map((select) => (
        <Controller
          key={select.name}
          control={control}
          name={select.name}
          render={({ field }) => (
            <Select
              label={select.label}
              labelPosition="side"
              value={field.value}
              options={[
                { value: "", label: select.all },
                ...(options.data?.[select.options] ?? []).map((option) => ({
                  value: String(option.id),
                  label: option.name,
                })),
              ]}
              onChange={field.onChange}
              disabled={options.data === undefined}
              className="w-40"
            />
          )}
        />
      ))}
      <PeriodField
        label="기간"
        fromInput={register("from")}
        toInput={register("to")}
        errorId={periodMessage && periodErrorId}
      />
    </FilterCard>
  );
}
