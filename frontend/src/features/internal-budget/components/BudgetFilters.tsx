import { zodResolver } from "@hookform/resolvers/zod";
import { useQuery } from "@tanstack/react-query";
import { useId } from "react";
import { Controller, useForm } from "react-hook-form";
import { FilterCard } from "../../../shared/components/ui/FilterCard";
import { PeriodField } from "../../../shared/components/ui/PeriodField";
import { Select } from "../../../shared/components/ui/Select";
import { internalOptionsQuery } from "../api/budget";
import { type BudgetFilterForm, budgetFilterFormSchema } from "../lib/search";

/** 선택 상자 이름과 "전체" 항목, 선택지 응답의 칸 */
const SELECTS = [
  {
    name: "project",
    label: "프로젝트",
    all: "전체 프로젝트",
    options: "projects",
  },
  { name: "model", label: "모델", all: "전체 모델", options: "models" },
] as const;

type BudgetFiltersProps = {
  values: BudgetFilterForm;
  onSubmit: (values: BudgetFilterForm) => void;
};

/** P-02 조회 조건. 조회 버튼을 눌러야 적용하고, 그때만 검증한다. */
export function BudgetFilters({ values, onSubmit }: BudgetFiltersProps) {
  const periodErrorId = useId();
  // 선택지를 못 불러와도 기간 조회는 쓸 수 있도록 화면 틀을 막지 않는다.
  const options = useQuery(internalOptionsQuery);
  const {
    control,
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<BudgetFilterForm>({
    defaultValues: values,
    resolver: zodResolver(budgetFilterFormSchema),
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
              className="w-44"
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
