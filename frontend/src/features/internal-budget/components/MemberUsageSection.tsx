import { useId } from "react";
import { Badge } from "../../../shared/components/ui/Badge";
import { Result } from "../../../shared/components/ui/Result";
import { PendingTable } from "./PendingTable";

const TITLE = "구성원별 Command Code 사용량";

/**
 * 구독료 관리 카드 안의 구성원 키별 Command Code 크레딧 사용량.
 * 값은 결제 기간 기준이라 조회 기간을 적용하지 않는다.
 * 구독에 포함된 크레딧이라 실제 지출이 아니므로 비용 합계에 더하지 않는다.
 */
export function MemberUsageSection() {
  const titleId = useId();
  return (
    <section aria-labelledby={titleId} className="mt-4">
      <div className="mx-6 border-t border-grey-200" />
      <header className="flex flex-wrap items-center gap-2 px-6 pt-5 pb-3">
        <h3 id={titleId} className="font-bold">
          {TITLE}
        </h3>
        <Badge tone="grey">결제 기간 기준</Badge>
        <p className="text-label text-grey-600">
          구독에 포함된 크레딧 사용량이라 비용 합계에는 넣지 않아요.
        </p>
      </header>
      <PendingTable
        caption={TITLE}
        columns={[
          { key: "member", header: "구성원" },
          { key: "credit", header: "사용 크레딧 (USD)", align: "right" },
          { key: "requests", header: "요청 수", align: "right" },
          { key: "input", header: "입력 Token", align: "right" },
          { key: "output", header: "출력 Token", align: "right" },
          { key: "remaining", header: "남은 크레딧 (USD)", align: "right" },
          { key: "billing", header: "결제 기간" },
        ]}
        empty={
          <Result
            title="등록된 구성원 키가 없어요"
            description="구성원의 Command Code 키가 등록되면 사용량이 보여요."
          />
        }
      />
    </section>
  );
}
