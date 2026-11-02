import { useMutation } from "@tanstack/react-query";
import { type ModelInfoChange, updateModelInfo } from "../api/models";
import { useApplyModelDetail } from "./useApplyModelDetail";

/** 표시 이름·용도 저장 */
export function useUpdateModelInfo(modelId: number) {
  return useMutation({
    mutationFn: (change: ModelInfoChange) => updateModelInfo(modelId, change),
    onSuccess: useApplyModelDetail(modelId),
  });
}
