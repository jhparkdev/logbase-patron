import { useQueryClient } from "@tanstack/react-query";
import {
  MODEL_LIST_KEY,
  type ModelDetail,
  modelDetailQuery,
} from "../api/models";

/** 서버가 돌려준 수정된 상세를 반영하는 함수. 상세는 바로 바꾸고, 상태·이름이 보이는 목록은 다시 불러옴 */
export function useApplyModelDetail(modelId: number) {
  const queryClient = useQueryClient();
  return (detail: ModelDetail) => {
    queryClient.setQueryData(modelDetailQuery(modelId).queryKey, detail);
    return queryClient.invalidateQueries({ queryKey: MODEL_LIST_KEY });
  };
}
