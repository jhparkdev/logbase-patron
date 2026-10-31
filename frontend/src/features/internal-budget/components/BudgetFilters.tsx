import { zodResolver } from "@hookform/resolvers/zod";
import { useId } from "react";
import { useForm } from "react-hook-form";
import { Button } from "../../../shared/components/ui/Button";
import { PeriodField } from "../../../shared/components/ui/PeriodField";
import { Select } from "../../../shared/components/ui/Select";
import { type Period, periodSchema } from "../../../shared/lib/period";

type BudgetFiltersProps = {
  period: Period;
  onSubmit: (period: Period) => void;
};

/**
 * P-02 조회 조건. 조회 버튼을 눌러야 적용한다.
 * 프로젝트·모델 선택지는 목록 API가 생기면 채운다. 그 전까지는 "전체"만 있고 바꿀 수 없다.
 */
export function BudgetFilters({ period, onSubmit }: BudgetFiltersProps) {
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
  const periodError = errors.from?.message ?? errors.to?.message;

  return (
    <form
      aria-label="조회 조건"
      noValidate
      onSubmit={handleSubmit(onSubmit)}
      className="rounded-2xl bg-white p-4"
    >
      <div className="flex flex-wrap items-end gap-3">
        <Select
          label="프로젝트"
          showLabel
          value=""
          options={[{ value: "", label: "전체 프로젝트" }]}
          onChange={() => {}}
          disabled
          className="w-50"
        />
        <Select
          label="모델"
          showLabel
          value=""
          options={[{ value: "", label: "전체 모델" }]}
          onChange={() => {}}
          disabled
          className="w-50"
        />
        <PeriodField
          label="기간"
          fromInput={register("from")}
          toInput={register("to")}
          errorId={periodError === undefined ? undefined : periodErrorId}
        />
        <Button type="submit" className="ml-auto">
          조회
        </Button>
      </div>
      {periodError !== undefined && (
        <p
          id={periodErrorId}
          role="alert"
          className="mt-2 text-label font-medium text-red-600"
        >
          {periodError}
        </p>
      )}
    </form>
  );
}
