import { getRouteApi } from "@tanstack/react-router";
import plusIcon from "../../../assets/plus.svg";
import { Badge } from "../../../shared/components/ui/Badge";
import { Button } from "../../../shared/components/ui/Button";
import { Result } from "../../../shared/components/ui/Result";
import { TextLink } from "../../../shared/components/ui/TextLink";
import { formatUsd } from "../../../shared/lib/format";
import { type SubscriptionRow, subscriptionRowsOptions } from "../api/budget";
import type { ListColumn } from "../lib/list";
import type { BudgetSearch } from "../lib/search";
import { subscriptionStatusBadge } from "../lib/view";
import { ListTable } from "./ListTable";
import { MemberUsageSection } from "./MemberUsageSection";

const TITLE = "구독료 관리";
/** 귀속 프로젝트가 없는 구독료 */
const UNASSIGNED_LABEL = "미배분";

const route = getRouteApi("/_app/internal-budget");

const COLUMNS: ListColumn<"subscriptions", SubscriptionRow>[] = [
  {
    key: "tool",
    header: "도구명",
    render: (row) => (
      <TextLink
        from="/internal-budget"
        to="/internal-budget"
        search={(prev) => ({ ...prev, subscription: row.subscription_id })}
        resetScroll={false}
      >
        {row.tool_name}
      </TextLink>
    ),
  },
  { key: "month", header: "적용 월", render: (row) => row.applied_month },
  {
    key: "amount",
    header: "금액 (USD)",
    align: "right",
    render: (row) => formatUsd(row.amount_usd, "summary"),
  },
  {
    key: "project",
    header: "귀속 프로젝트",
    render: (row) =>
      row.project_id === null ? (
        <span className="text-grey-600">{UNASSIGNED_LABEL}</span>
      ) : (
        row.project_name
      ),
  },
  {
    key: "status",
    header: "상태",
    render: (row) => {
      const badge = subscriptionStatusBadge(row.status);
      return <Badge tone={badge.tone}>{badge.label}</Badge>;
    },
  },
];

type SubscriptionTableProps = {
  search: BudgetSearch;
  refreshing: boolean;
  onPageChange?: (page: number) => void;
};

/**
 * 조회 기간이 걸치는 달의 월 구독료. 요약 화면에서는 최근 적용 월 N건과 구성원별 Command Code 사용량을
 * 함께 보여 준다. 등록 버튼은 주소에 남겨 등록 패널을 연다.
 */
export function SubscriptionTable({
  search,
  refreshing,
  onPageChange,
}: SubscriptionTableProps) {
  const navigate = route.useNavigate();
  return (
    <ListTable
      view="subscriptions"
      title={TITLE}
      description={`${onPageChange ? "" : "최근 적용 월 기준 · "}도구명을 누르면 내용을 고칠 수 있어요.`}
      action={
        <Button
          variant="secondary"
          size="sm"
          icon={plusIcon}
          onClick={() =>
            navigate({
              search: (prev) => ({ ...prev, subscription: "new" }),
              resetScroll: false,
            })
          }
        >
          구독료 등록
        </Button>
      }
      errorTitle="구독료 관리를 불러오지 못했어요"
      query={subscriptionRowsOptions(search)}
      columns={COLUMNS}
      rowKey={(row) => String(row.subscription_id)}
      empty={
        <Result
          title="등록된 구독료가 없어요"
          description="구독료를 등록하면 월 구독료와 총 관리 비용에 반영돼요."
        />
      }
      refreshing={refreshing}
      onPageChange={onPageChange}
    >
      <MemberUsageSection />
    </ListTable>
  );
}
