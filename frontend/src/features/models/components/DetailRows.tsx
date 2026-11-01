import type { ReactNode } from "react";

/** 항목 이름과 값을 두 줄 격자로 나열 */
export function Rows({ children }: { children: ReactNode }) {
  return (
    <dl className="grid grid-cols-[8.5rem_1fr] items-center gap-x-4 gap-y-2.5 text-body-sm">
      {children}
    </dl>
  );
}

export function Row({
  label,
  children,
}: {
  label: string;
  children: ReactNode;
}) {
  return (
    <>
      <dt className="text-grey-600">{label}</dt>
      <dd className="tabular-nums">{children}</dd>
    </>
  );
}
