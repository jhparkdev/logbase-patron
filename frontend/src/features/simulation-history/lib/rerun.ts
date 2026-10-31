import type { HistoryDetailView } from "./presentation";

export function rerunBlockReason(
  detail: HistoryDetailView,
): string | undefined {
  if (detail.input.kind === "missing")
    return "저장된 입력을 확인할 수 없어 재실행할 수 없어요.";
  if (!detail.input.prompt.trim())
    return "저장된 Prompt가 없어 재실행할 수 없어요.";
  if (detail.input.attachments.some((file) => !file.available))
    return "저장된 이미지에 접근할 수 없어 재실행할 수 없어요.";
  if (
    !detail.models.length ||
    detail.models.some((model) => model.currentState === "unknown")
  )
    return "현재 모델 정보를 확인한 뒤 재실행할 수 있어요.";
}
