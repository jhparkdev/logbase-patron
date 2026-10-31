import { getRouteApi } from "@tanstack/react-router";
import plusIcon from "../../../assets/plus.svg";
import { Button } from "../../../shared/components/ui/Button";
import { Result } from "../../../shared/components/ui/Result";
import { SectionCard } from "../../../shared/components/ui/SectionCard";
import type { ListColumn, ListControls } from "../lib/list";
import { MemberUsageSection } from "./MemberUsageSection";
import { PendingTable } from "./PendingTable";
import { ViewAllLink } from "./ViewAllLink";

const TITLE = "구독료 관리";

const route = getRouteApi("/_app/internal-budget");

const COLUMNS: ListColumn<"subscriptions">[] = [
  { key: "tool", header: "도구명" },
  { key: "month", header: "적용 월" },
  { key: "amount", header: "금액 (USD)", align: "right" },
  { key: "project", header: "귀속 프로젝트" },
  { key: "status", header: "상태" },
];

/**
 * 월 구독료 목록. 요약 화면에서는 아래에 구성원별 Command Code 사용량을 함께 보여 주고,
 * list가 있으면 구독료 전체 목록만 보여 준다. 등록 버튼은 주소에 남겨 등록 패널을 연다.
 */
export function SubscriptionTable({ list }: { list?: ListControls }) {
  const navigate = route.useNavigate();
  return (
    <SectionCard
      title={TITLE}
      description="도구명을 누르면 내용을 고칠 수 있어요."
      action={
        <div className="flex items-center gap-4">
          {!list && <ViewAllLink view="subscriptions" title={TITLE} />}
          <Button
            variant="secondary"
            size="sm"
            icon={plusIcon}
            onClick={() =>
              navigate({ search: (prev) => ({ ...prev, subscription: "new" }) })
            }
          >
            구독료 등록
          </Button>
        </div>
      }
    >
      <PendingTable
        caption={TITLE}
        columns={COLUMNS}
        empty={
          <Result
            title="등록된 구독료가 없어요"
            description="구독료를 등록하면 월 구독료와 총 관리 비용에 반영돼요."
          />
        }
        list={list}
      />
      {!list && <MemberUsageSection />}
    </SectionCard>
  );
}
