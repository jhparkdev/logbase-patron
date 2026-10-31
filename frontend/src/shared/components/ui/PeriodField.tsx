import type { ComponentProps } from "react";

type PeriodFieldProps = {
  /** 묶음 이름. 예: 기간 */
  label: string;
  /** 시작일 칸에 넘길 속성. React Hook Form의 register("from") 결과를 그대로 넘길 수 있다. */
  fromInput: ComponentProps<"input">;
  toInput: ComponentProps<"input">;
  /**
   * 기간 오류 문구의 id. 있으면 두 칸을 잘못된 입력으로 표시하고 문구와 연결한다.
   * 문구는 쓰는 쪽이 그린다. 문구 때문에 칸 높이가 늘어 옆 칸과 줄이 어긋나지 않게 하려는 것이다.
   */
  errorId?: string;
};

const INPUT_CLASS =
  "h-9.5 rounded-control border border-neutral-weak bg-grey-50 px-3 text-body-sm focus-visible:border-brand focus-visible:outline-none aria-invalid:border-red-500";

/** 시작일 ~ 종료일 두 칸. 날짜는 KST 달력 기준 "YYYY-MM-DD"다. */
export function PeriodField({
  label,
  fromInput,
  toInput,
  errorId,
}: PeriodFieldProps) {
  const invalidProps = {
    "aria-invalid": errorId !== undefined,
    "aria-describedby": errorId,
  };

  return (
    <fieldset className="min-w-0">
      <legend className="mb-1.5 text-label font-medium text-grey-700">
        {label}
      </legend>
      <div className="flex items-center gap-2">
        <input
          type="date"
          aria-label="시작일"
          className={INPUT_CLASS}
          {...invalidProps}
          {...fromInput}
        />
        <span aria-hidden="true" className="text-grey-500">
          ~
        </span>
        <input
          type="date"
          aria-label="종료일"
          className={INPUT_CLASS}
          {...invalidProps}
          {...toInput}
        />
      </div>
    </fieldset>
  );
}
