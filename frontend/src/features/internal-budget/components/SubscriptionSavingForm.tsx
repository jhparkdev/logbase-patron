import { ApiError } from "../../../shared/api/client";
import type { SubscriptionProject } from "../api/budget";
import {
  type SubscriptionSaveTarget,
  useSaveSubscription,
} from "../hooks/useSaveSubscription";
import type { SubscriptionFormValues } from "../lib/forms";
import { SubscriptionForm } from "./SubscriptionForm";

const SAVE_FAILED_MESSAGE = "구독료를 저장하지 못했어요. 다시 시도해 주세요.";

/** 등록·수정 폼이 함께 받는 것. 패널이 선택지와 닫기를 채운다. */
export type PanelFormProps = {
  projects?: SubscriptionProject[];
  onClose: () => void;
};

type SavingFormProps = PanelFormProps & { target: SubscriptionSaveTarget } & (
    | { defaultMonth: string; editing?: never }
    | { editing: SubscriptionFormValues; defaultMonth?: never }
  );

/** 저장 상태(진행 중, 서버 거절 문구)를 폼에 넘긴다. 성공하면 패널을 닫는다. */
export function SavingForm({ target, onClose, ...formProps }: SavingFormProps) {
  const save = useSaveSubscription(target, formProps.projects ?? [], onClose);
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
