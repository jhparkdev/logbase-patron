import statusFailedIcon from "../../../assets/statusFailed.svg";
import statusNeutralIcon from "../../../assets/statusNeutral.svg";
import statusSuccessIcon from "../../../assets/statusSuccess.svg";
import statusTimeoutIcon from "../../../assets/statusTimeout.svg";
import type { components } from "../../api/schema";
import { executionStatus } from "../../lib/request";
import { Icon } from "./Icon";

/** 글자색은 상태 배지(Badge)와 같은 단계를 쓴다. */
const TONE = {
  green: { icon: statusSuccessIcon, className: "text-green-700" },
  red: { icon: statusFailedIcon, className: "text-red-600" },
  yellow: { icon: statusTimeoutIcon, className: "text-yellow-700" },
  grey: { icon: statusNeutralIcon, className: "text-grey-600" },
} as const;

/** 비용 상태 배지(바탕 있는 알약)와 구분하려고 바탕 없이 아이콘과 색 글자로 그린다(docs/design/tokens.md). */
export function ExecutionBadge({
  status,
}: {
  status: components["schemas"]["RequestStatus"];
}) {
  const { label, tone } = executionStatus(status);
  return (
    <span
      className={`inline-flex items-center gap-1 text-label font-bold whitespace-nowrap ${TONE[tone].className}`}
    >
      <Icon src={TONE[tone].icon} className="size-4" />
      {label}
    </span>
  );
}
