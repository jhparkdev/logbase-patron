import plusIcon from "../../../assets/plus.svg";
import { Button } from "../../../shared/components/ui/Button";
import { Result } from "../../../shared/components/ui/Result";
import { SectionCard } from "../../../shared/components/ui/SectionCard";
import { PendingTable } from "./PendingTable";

const TITLE = "구독료 관리";

/** 월 구독료 목록. 등록 버튼은 등록 패널이 생기면 켠다. */
export function SubscriptionTable() {
  return (
    <SectionCard
      title={TITLE}
      description="도구명을 누르면 내용을 고칠 수 있어요."
      action={
        <Button variant="secondary" size="sm" icon={plusIcon} disabled>
          구독료 등록
        </Button>
      }
    >
      <PendingTable
        caption={TITLE}
        columns={[
          { key: "tool", header: "도구명" },
          { key: "month", header: "적용 월" },
          { key: "amount", header: "금액 (USD)", align: "right" },
          { key: "project", header: "귀속 프로젝트" },
          { key: "status", header: "상태" },
        ]}
        empty={
          <Result
            title="등록된 구독료가 없어요"
            description="구독료를 등록하면 월 구독료와 총 관리 비용에 반영돼요."
          />
        }
      />
    </SectionCard>
  );
}
