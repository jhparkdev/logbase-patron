import { useQuery } from "@tanstack/react-query";
import { ApiError } from "../../../shared/api/client";
import { Button } from "../../../shared/components/ui/Button";
import { Result } from "../../../shared/components/ui/Result";
import { SidePanel } from "../../../shared/components/ui/SidePanel";
import { Skeleton } from "../../../shared/components/ui/Skeleton";
import {
  subscriptionDetailQuery,
  subscriptionOptionsQuery,
} from "../api/budget";
import { subscriptionFormValues } from "../lib/forms";
import { type PanelFormProps, SavingForm } from "./SubscriptionSavingForm";

type SubscriptionPanelProps = {
  /** "new"면 등록, 번호면 그 구독료 수정 */
  subscription: "new" | number;
  /** 등록할 때 적용 월의 처음 값 "YYYY-MM" */
  month: string;
  onClose: () => void;
};

/** 구독료 등록·수정 패널. 저장에 성공하면 닫힌다. */
export function SubscriptionPanel({
  subscription,
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
      <EditingForm subscriptionId={subscription} {...common} />
    </SidePanel>
  );
}

/** 수정할 구독료는 단건 조회로 받는다. 주소를 공유하거나 새로 고쳐도 열린다. */
function EditingForm({
  subscriptionId,
  ...common
}: PanelFormProps & { subscriptionId: number }) {
  const row = useQuery(subscriptionDetailQuery(subscriptionId));
  if (row.isPending) {
    return <Skeleton className="h-64" />;
  }
  if (row.isError) {
    return <DetailError error={row.error} onRetry={() => row.refetch()} />;
  }
  const before = subscriptionFormValues(row.data);
  return (
    <SavingForm
      target={{ id: subscriptionId, before }}
      editing={before}
      {...common}
    />
  );
}

/** 없는 번호는 다시 해도 결과가 같아 다시 시도를 두지 않는다. */
function DetailError({
  error,
  onRetry,
}: {
  error: Error;
  onRetry: () => void;
}) {
  if (error instanceof ApiError && error.code === "NOT_FOUND") {
    return (
      <Result
        title="구독료를 찾을 수 없어요"
        description="목록에서 도구명을 눌러 열어 주세요."
      />
    );
  }
  return (
    <Result
      title="구독료를 불러오지 못했어요"
      description="잠시 후 다시 시도해 주세요."
      action={
        <Button variant="secondary" size="sm" onClick={onRetry}>
          다시 시도
        </Button>
      }
    />
  );
}
