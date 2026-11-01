import { Button } from "../../../shared/components/ui/Button";
import { Dialog } from "../../../shared/components/ui/Dialog";
import { FormHint } from "../../../shared/components/ui/PanelForm";
import type { ModelDetail } from "../api/models";
import { useChangeModelStatus } from "../hooks/useChangeModelStatus";
import { type ChangeableStatus, statusChangeText } from "../lib/view";
import { FormError } from "./FormError";

const CHANGE_FAILED_MESSAGE = "상태를 바꾸지 못했어요. 다시 시도해 주세요.";

type StatusChangeDialogProps = {
  model: Pick<ModelDetail, "model_id" | "display_name">;
  target: ChangeableStatus;
  onClose: () => void;
};

/** 상태 변경 확인창. 모델 상태는 시뮬레이터 선택에 영향을 주므로 확인 뒤에 요청하고, 서버가 거절하면 이유를 창 안에 보여 줌 */
export function StatusChangeDialog({
  model,
  target,
  onClose,
}: StatusChangeDialogProps) {
  const change = useChangeModelStatus(model.model_id);
  const text = statusChangeText(target);
  return (
    <Dialog
      open
      title={text.action}
      onClose={onClose}
      action={
        // 누르는 즉시 비활성화해 같은 요청이 두 번 가지 않게 함
        <Button
          disabled={change.isPending}
          onClick={() => change.mutate(target, { onSuccess: onClose })}
        >
          {change.isPending ? "처리 중" : text.action}
        </Button>
      }
    >
      <div className="flex flex-col gap-4">
        <p>
          “{model.display_name}” 모델을 {text.action}할까요?
        </p>
        <FormHint>{text.hint}</FormHint>
        {change.isError && (
          <FormError error={change.error} fallback={CHANGE_FAILED_MESSAGE} />
        )}
      </div>
    </Dialog>
  );
}
