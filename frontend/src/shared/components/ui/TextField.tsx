import { type ComponentProps, useId } from "react";

type TextFieldProps = Omit<
  ComponentProps<"input">,
  "id" | "aria-invalid" | "aria-describedby" | "className"
> & {
  label: string;
  /** 제출 검증에서 나온 문구. 있으면 칸을 빨간 테두리로 표시하고 아래에 보여 준다. */
  error?: string;
  /** 놓이는 자리에서 정할 값. 예: w-full */
  className?: string;
};

/** 라벨이 붙은 한 줄 입력 칸. 규격은 docs/design/tokens.md "입력 칸, 선택 상자" */
export function TextField({
  label,
  error,
  className = "",
  ...props
}: TextFieldProps) {
  const id = useId();
  const errorId = `${id}-error`;
  return (
    <div className={`flex flex-col gap-1.5 ${className}`}>
      <label htmlFor={id} className="text-label font-medium text-grey-600">
        {label}
      </label>
      <input
        id={id}
        aria-invalid={error ? true : undefined}
        aria-describedby={error ? errorId : undefined}
        className={`h-9.5 w-full rounded-control border bg-grey-50 px-3 text-body-sm placeholder:text-grey-500 focus-visible:border-brand focus-visible:outline-none ${error ? "border-red-500" : "border-neutral-weak"}`}
        {...props}
      />
      {error && (
        <p id={errorId} className="text-caption text-red-600">
          {error}
        </p>
      )}
    </div>
  );
}
