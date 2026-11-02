import { useId } from "react";
import type { components } from "../../../shared/api/schema";
import {
  formatCount,
  formatUsd,
  isZeroAmount,
} from "../../../shared/lib/format";
import { serviceBudgetShare } from "../lib/panel";

type Service = components["schemas"]["CustomerServiceUsage"];

/**
 * 서비스별 사용액. 확정과 추정은 화면에서 더하지 않고 나눠 보여 준다.
 * 막대는 서비스별 예산이 아니라, 고객 예산에서 그 서비스가 차지하는 비중이다.
 */
export function CustomerServiceList({ services }: { services: Service[] }) {
  const headingId = useId();
  if (services.length === 0) {
    return null;
  }
  return (
    <section className="flex flex-col gap-3">
      <div className="flex items-baseline justify-between gap-2">
        <h3 id={headingId} className="font-bold">
          서비스별 사용액
        </h3>
        <span className="text-caption text-grey-600">
          막대는 예산 대비 비중
        </span>
      </div>
      <ul aria-labelledby={headingId} className="flex flex-col gap-4">
        {services.map((service) => {
          const share = serviceBudgetShare(service.budget_share_pct);
          return (
            <li key={service.service_id} className="flex flex-col gap-1.5">
              <div className="flex items-baseline justify-between gap-3 text-body-sm">
                <span className="font-medium">{service.service_name}</span>
                <span className="text-grey-600 tabular-nums">
                  {share.label}
                </span>
              </div>
              {share.width !== undefined && (
                <div
                  aria-hidden="true"
                  className="h-1.5 rounded-full bg-grey-100"
                >
                  <div
                    className="h-full rounded-full bg-brand"
                    // 너비는 서버가 준 비중에서 정해지므로 inline style로 둔다.
                    style={{ width: `${share.width}%` }}
                  />
                </div>
              )}
              <p className="text-caption text-grey-600 tabular-nums">
                확정 {formatUsd(service.confirmed_cost_usd, "summary")} · 추정{" "}
                {isZeroAmount(service.estimated_cost_usd) ? "" : "≈ "}
                {formatUsd(service.estimated_cost_usd, "summary")} · 미확인{" "}
                {formatCount(service.unknown_cost_count)}건
              </p>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
