import { useMutation, useQueryClient } from "@tanstack/react-query";
import {
  MODEL_LIST_KEY,
  MODEL_PROVIDERS_KEY,
  OPENROUTER_MODELS_KEY,
  registerModel,
} from "../api/models";

/** 신규 모델 등록 */
export function useRegisterModel() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: registerModel,
    // 새 모델이 목록과 제공사 선택지에 보이고, 검색 결과의 이미 등록됨이 바뀜
    onSuccess: () =>
      Promise.all(
        [MODEL_LIST_KEY, MODEL_PROVIDERS_KEY, OPENROUTER_MODELS_KEY].map(
          (queryKey) => queryClient.invalidateQueries({ queryKey }),
        ),
      ),
  });
}
