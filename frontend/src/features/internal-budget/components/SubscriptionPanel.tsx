import { useQuery } from "@tanstack/react-query";
import { ApiError } from "../../../shared/api/client";
import { Result } from "../../../shared/components/ui/Result";
import { SidePanel } from "../../../shared/components/ui/SidePanel";
import { Skeleton } from "../../../shared/components/ui/Skeleton";
import {
  type SubscriptionProject,
  subscriptionOptionsQuery,
  subscriptionRowsOptions,
} from "../api/budget";
import {
  type SubscriptionSaveTarget,
  useSaveSubscription,
} from "../hooks/useSaveSubscription";
import {
  type SubscriptionFormValues,
  subscriptionFormValues,
} from "../lib/forms";
import type { BudgetSearch } from "../lib/search";
import { SubscriptionForm } from "./SubscriptionForm";

const SAVE_FAILED_MESSAGE = "구독료를 저장하지 못했어요. 다시 시도해 주세요.";

type SubscriptionPanelProps = {
  /** "new"면 등록, 번호면 그 구독료 수정 */
  subscription: "new" | number;
  /** 수정할 행을 찾을 구독료 표의 조회 조건. 단건 조회 API가 없어 표가 받은 목록에서 찾는다. */
  search: BudgetSearch;
  /** 등록할 때 적용 월의 처음 값 "YYYY-MM" */
  month: string;
  onClose: () => void;
};

/** 구독료 등록·수정 패널. 저장에 성공하면 닫힌다. */
export function SubscriptionPanel({
  subscription,
  search,
  month,
  onClose,
}: SubscriptionPanelProps) {
  const options = useQuery(subscriptionOptionsQuery);
  const common = { projects: options.data?.projects, onClose };
  if (subscription === "new") {
    return (
      <SidePanel title="구독료 등록" onClose={onClose}>
        <SavingForm target="new" defaultMonth={month} {...common} />
      </SidePanel>
    );
  }
  return (
    <SidePanel title="구독료 수정" onClose={onClose}>
      <EditingForm subscriptionId={subscription} search={search} {...common} />
    </SidePanel>
  );
}

type CommonProps = { projects?: SubscriptionProject[]; onClose: () => void };

/** 수정할 행은 구독료 표와 같은 조회(이미 캐시된 목록)에서 찾는다. */
function EditingForm({
  subscriptionId,
  search,
  ...common
}: CommonProps & { subscriptionId: number; search: BudgetSearch }) {
  const rows = useQuery(subscriptionRowsOptions(search));
  if (rows.isPending) {
    return <Skeleton className="h-64" />;
  }
  const row = rows.data?.items.find(
    (item) => item.subscription_id === subscriptionId,
  );
  if (row === undefined) {
    return (
      <Result
        title="이 구독료는 지금 목록에 없어요"
        description="목록에서 도구명을 눌러 열어 주세요."
      />
    );
  }
  const before = subscriptionFormValues(row);
  return (
    <SavingForm
      target={{ id: subscriptionId, before }}
      editing={before}
      {...common}
    />
  );
}

type SavingFormProps = CommonProps & { target: SubscriptionSaveTarget } & (
    | { defaultMonth: string; editing?: never }
    | { editing: SubscriptionFormValues; defaultMonth?: never }
  );

/** 저장 상태(진행 중, 서버 거절 문구)를 폼에 넘긴다. 성공하면 패널을 닫는다. */
function SavingForm({ target, onClose, ...formProps }: SavingFormProps) {
  const save = useSaveSubscription(target, onClose);
  return (
    <SubscriptionForm
      {...formProps}
      submitting={save.isPending}
      errorMessage={
        save.isError
          ? save.error instanceof ApiError
            ? save.error.message
            : SAVE_FAILED_MESSAGE
          : undefined
      }
      onSubmit={save.mutate}
      onClose={onClose}
    />
  );
}
