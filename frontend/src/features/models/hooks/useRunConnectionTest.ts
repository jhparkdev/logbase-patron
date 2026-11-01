import { useMutation, useQueryClient } from "@tanstack/react-query";
import {
  MODEL_LIST_KEY,
  modelDetailQuery,
  runConnectionTest,
} from "../api/models";

/** 연결 테스트 실행. 끝나면 마지막 테스트가 바뀐 상세와 목록을 다시 불러옴 */
export function useRunConnectionTest(modelId: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (prompt: string) => runConnectionTest(modelId, prompt),
    // 결과를 먼저 보여 주려고 다시 불러오기를 기다리지 않음
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: modelDetailQuery(modelId).queryKey,
      });
      void queryClient.invalidateQueries({ queryKey: MODEL_LIST_KEY });
    },
  });
}
