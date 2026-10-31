import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { Button } from "../../../shared/components/ui/Button";
import { PeriodField } from "../../../shared/components/ui/PeriodField";
import { Select } from "../../../shared/components/ui/Select";
import { type Period, periodSchema } from "../../../shared/lib/period";

type BudgetFiltersProps = {
  period: Period;
  onSubmit: (period: Period) => void;
};

const FIELD_LABEL_CLASS =
  "flex flex-col gap-1.5 text-label font-medium text-grey-700";

/**
 * P-02 조회 조건. 조회 버튼을 눌러야 적용한다.
 * 프로젝트·모델 선택지는 목록 API가 생기면 채운다. 그 전까지는 "전체"만 있고 바꿀 수 없다.
 */
export function BudgetFilters({ period, onSubmit }: BudgetFiltersProps) {
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<Period>({
    defaultValues: period,
    resolver: zodResolver(periodSchema),
    reValidateMode: "onSubmit",
  });

  return (
    <form
      aria-label="조회 조건"
      noValidate
      onSubmit={handleSubmit(onSubmit)}
      className="flex flex-wrap items-start gap-3 rounded-2xl bg-white p-4"
    >
      {/* 화면 낭독기는 Select의 이름(label)을 읽으므로, 위쪽 글자는 보이게만 두고 읽지 않게 한다. */}
      <div className={FIELD_LABEL_CLASS}>
        <span aria-hidden="true">프로젝트</span>
        <Select
          label="프로젝트"
          value=""
          options={[{ value: "", label: "전체 프로젝트" }]}
          onChange={() => {}}
          disabled
          className="w-50"
        />
      </div>
      <div className={FIELD_LABEL_CLASS}>
        <span aria-hidden="true">모델</span>
        <Select
          label="모델"
          value=""
          options={[{ value: "", label: "전체 모델" }]}
          onChange={() => {}}
          disabled
          className="w-50"
        />
      </div>
      <PeriodField
        label="기간"
        fromInput={register("from")}
        toInput={register("to")}
        error={errors.from?.message ?? errors.to?.message}
      />
      {/* 라벨 줄 높이만큼 내려 입력 칸과 같은 줄에 둔다. 기간 오류 문구가 늘어나도 버튼은 제자리에 있다. */}
      <Button type="submit" className="mt-6.5 ml-auto">
        조회
      </Button>
    </form>
  );
}
