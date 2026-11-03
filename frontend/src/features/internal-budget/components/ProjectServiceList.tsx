import { useId } from "react";
import type { components } from "../../../shared/api/schema";
import { serviceBudgetShare } from "../../../shared/lib/budget";
import {
  formatCount,
  formatUsd,
  isZeroAmount,
} from "../../../shared/lib/format";

type Service = components["schemas"]["ProjectServiceUsage"];

/**
 * 서비스별 API 사용액. 서버가 서비스별 합계를 주지 않아 금액은 확정만 적고, 추정·미확인은 아래 줄에 따로 둔다.
 * 막대는 서비스별 예산이 아니라 프로젝트 예산에서 그 서비스가 차지하는 비중이다.
 */
export function ProjectServiceList({ services }: { services: Service[] }) {
  const headingId = useId();
  if (services.length === 0) {
    return null;
  }
  return (
    <section className="flex flex-col gap-3">
      <div className="flex items-baseline justify-between gap-2">
        <h3 id={headingId} className="font-bold">
          서비스별 API 사용액
        </h3>
        <span className="text-caption text-grey-600">
          확정 기준 · 예산 대비 비중
        </span>
      </div>
      <ul aria-labelledby={headingId} className="flex flex-col gap-3">
        {services.map((service) => {
          const share = serviceBudgetShare(service.budget_share_pct);
          const notes = [
            isZeroAmount(service.estimated_cost_usd)
              ? undefined
              : `추정 ≈ ${formatUsd(service.estimated_cost_usd, "summary")}`,
            service.unknown_cost_count > 0
              ? `미확인 ${formatCount(service.unknown_cost_count)}건`
              : undefined,
          ].filter(Boolean);
          return (
            <li
              key={service.service_id}
              className="grid grid-cols-[minmax(7rem,11rem)_1fr_auto_3rem] items-center gap-x-3 gap-y-1 text-body-sm"
            >
              <span
                className="truncate font-medium"
                title={service.service_name}
              >
                {service.service_name}
              </span>
              <div
                aria-hidden="true"
                className="h-1.5 rounded-full bg-grey-100"
              >
                {share.width !== undefined && (
                  <div
                    className="h-full rounded-full bg-brand"
                    // 너비는 서버가 준 비중에서 정해지므로 inline style로 둔다.
                    style={{ width: `${share.width}%` }}
                  />
                )}
              </div>
              <span className="font-semibold tabular-nums">
                {formatUsd(service.confirmed_cost_usd, "summary")}
              </span>
              <span className="text-right text-grey-600 tabular-nums">
                {share.percent === undefined ? "—" : `${share.percent}%`}
              </span>
              {notes.length > 0 && (
                <p className="col-span-full text-caption text-grey-600 tabular-nums">
                  {notes.join(" · ")}
                </p>
              )}
            </li>
          );
        })}
      </ul>
    </section>
  );
}
