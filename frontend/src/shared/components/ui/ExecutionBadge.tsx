import type { components } from "../../api/schema";
import { executionStatus } from "../../lib/request";

/** 비용 상태 배지와 모양을 구분하려고 테두리와 점으로 그린다(docs/design/tokens.md). */
export function ExecutionBadge({
  status,
}: {
  status: components["schemas"]["RequestStatus"];
}) {
  const { label, dotClass } = executionStatus(status);
  return (
    <span className="inline-flex h-6 items-center gap-1.5 rounded-full border border-grey-200 px-2 text-caption font-bold whitespace-nowrap">
      <span
        aria-hidden="true"
        className={`size-1.5 rounded-full ${dotClass}`}
      />
      {label}
    </span>
  );
}
