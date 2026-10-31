import { type ComponentProps, useId } from "react";

type PeriodFieldProps = {
  /** 묶음 이름. 예: 기간 */
  label: string;
  /** 시작일 칸에 넘길 속성. React Hook Form의 register("from") 결과를 그대로 넘길 수 있다. */
  fromInput: ComponentProps<"input">;
  toInput: ComponentProps<"input">;
  /** 기간 검증 문구. 있으면 두 칸을 잘못된 입력으로 표시한다. */
  error?: string;
};

const INPUT_CLASS =
  "h-9.5 rounded-control border border-neutral-weak bg-grey-50 px-3 text-body-sm focus-visible:border-brand focus-visible:outline-none aria-invalid:border-red-500";

/** 시작일 ~ 종료일 두 칸. 날짜는 KST 달력 기준 "YYYY-MM-DD"다. */
export function PeriodField({
  label,
  fromInput,
  toInput,
  error,
}: PeriodFieldProps) {
  const errorId = useId();
  const invalidProps = {
    "aria-invalid": error !== undefined,
    "aria-describedby": error === undefined ? undefined : errorId,
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
      {error !== undefined && (
        <p
          id={errorId}
          role="alert"
          className="mt-1.5 text-label font-medium text-red-600"
        >
          {error}
        </p>
      )}
    </fieldset>
  );
}
