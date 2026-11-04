import type { ReactNode } from "react";

/** 조건 입력 화면의 단계 제목. 번호 원 + 제목 + 오른쪽 도구. */
export function StepHeading({
  number,
  title,
  children,
}: {
  number: number;
  title: string;
  children?: ReactNode;
}) {
  return (
    <div className="flex flex-wrap items-center gap-3">
      <span
        aria-hidden="true"
        className="grid size-7 shrink-0 place-items-center rounded-full bg-brand text-body-sm font-bold text-white"
      >
        {number}
      </span>
      <h2 className="text-section font-bold">
        <span className="sr-only">{number}단계 </span>
        {title}
      </h2>
      {children}
    </div>
  );
}
