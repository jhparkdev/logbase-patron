import { useMutation } from "@tanstack/react-query";
import { changeModelStatus } from "../api/models";
import type { ChangeableStatus } from "../lib/view";
import { useApplyModelDetail } from "./useApplyModelDetail";

/** 모델 상태 변경 */
export function useChangeModelStatus(modelId: number) {
  return useMutation({
    mutationFn: (status: ChangeableStatus) =>
      changeModelStatus(modelId, status),
    onSuccess: useApplyModelDetail(modelId),
  });
}
