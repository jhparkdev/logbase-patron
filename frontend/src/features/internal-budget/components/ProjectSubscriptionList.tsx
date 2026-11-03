import { useId } from "react";
import type { components } from "../../../shared/api/schema";
import { Badge } from "../../../shared/components/ui/Badge";
import { formatUsd } from "../../../shared/lib/format";
import { subscriptionStatusBadge } from "../lib/view";

type Detail = Pick<
  components["schemas"]["ProjectUsageDetail"],
  "subscriptions" | "subscription_usd"
>;

/** 이 프로젝트에 귀속된 구독료. 합계는 서버 값이고 해지된 것도 들어 있어 상태 배지로 구분한다 */
export function ProjectSubscriptionList({ detail }: { detail: Detail }) {
  const headingId = useId();
  if (detail.subscriptions.length === 0) {
    return null;
  }
  return (
    <section className="flex flex-col gap-3">
      <div className="flex items-baseline justify-between gap-2">
        <h3 id={headingId} className="font-bold">
          귀속 구독료
        </h3>
        <span className="text-caption text-grey-600 tabular-nums">
          합계 {formatUsd(detail.subscription_usd, "summary")} USD
        </span>
      </div>
      <ul aria-labelledby={headingId} className="flex flex-col gap-2">
        {detail.subscriptions.map((subscription) => {
          const badge = subscriptionStatusBadge(subscription.status);
          return (
            <li
              key={subscription.subscription_id}
              className="flex items-center gap-3 rounded-2xl border border-grey-100 p-3 text-body-sm"
            >
              <span
                aria-hidden="true"
                className="grid size-8 shrink-0 place-items-center rounded-full bg-teal-50 font-bold text-teal-700 uppercase"
              >
                {subscription.tool_name.charAt(0)}
              </span>
              <span className="flex-1 truncate font-medium">
                {subscription.tool_name}
              </span>
              <Badge tone={badge.tone}>{badge.label}</Badge>
              <span className="font-semibold tabular-nums">
                {formatUsd(subscription.amount_usd, "summary")}
              </span>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
