import { TextLink } from "../../../shared/components/ui/TextLink";
import type { UsageListView } from "../lib/search";
import { CustomerUsageTable } from "./CustomerUsageTable";
import { RequestTable } from "./RequestTable";

type UsageFullListProps = {
  view: UsageListView;
  budgetMonth: string;
};

/** 전체보기 화면. 고른 목록 하나만 보여 준다. */
export function UsageFullList({ view, budgetMonth }: UsageFullListProps) {
  return (
    <>
      <TextLink
        from="/customer-usage"
        to="/customer-usage"
        search={(prev) => ({ ...prev, view: undefined })}
        className="self-start text-body-sm"
      >
        <span aria-hidden="true">‹ </span>요약으로 돌아가기
      </TextLink>
      {view === "customers" ? (
        <CustomerUsageTable budgetMonth={budgetMonth} fullView />
      ) : (
        <RequestTable fullView />
      )}
    </>
  );
}
