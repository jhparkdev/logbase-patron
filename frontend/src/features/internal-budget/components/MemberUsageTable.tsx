import { Result } from "../../../shared/components/ui/Result";
import { SectionCard } from "../../../shared/components/ui/SectionCard";
import { PendingTable } from "./PendingTable";

const TITLE = "구성원별 Command Code 사용량";

/**
 * 구성원 키별 Command Code 크레딧 사용량. 값은 결제 기간 기준이라 조회 기간을 적용하지 않는다.
 * 구독에 포함된 크레딧이라 실제 지출이 아니므로 비용 합계에 더하지 않는다.
 */
export function MemberUsageTable() {
  return (
    <SectionCard
      title={TITLE}
      description="결제 기간 기준 · 구독에 포함된 크레딧 사용량이라 비용 합계에는 넣지 않아요."
    >
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
    </SectionCard>
  );
}
