import { useMutation, useQueryClient } from "@tanstack/react-query";
import {
  MODEL_LIST_KEY,
  type ModelInfoChange,
  modelDetailQuery,
  updateModelInfo,
} from "../api/models";

/** 표시 이름·용도 저장. 성공하면 응답으로 상세를 바꾸고, 이름이 보이는 목록만 다시 불러옴 */
export function useUpdateModelInfo(modelId: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (change: ModelInfoChange) => updateModelInfo(modelId, change),
    onSuccess: (detail) => {
      queryClient.setQueryData(modelDetailQuery(modelId).queryKey, detail);
      return queryClient.invalidateQueries({ queryKey: MODEL_LIST_KEY });
    },
  });
}
