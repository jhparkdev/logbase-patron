import { useMutation, useQueryClient } from "@tanstack/react-query";
import {
  createSubscription,
  SUBSCRIPTION_AFFECTED_KEYS,
  updateSubscription,
} from "../api/budget";
import {
  type SubscriptionFormValues,
  subscriptionCreateBody,
  subscriptionUpdateBody,
} from "../lib/forms";

/** 등록("new") 또는 수정(번호와 수정 전 값. 바꾼 칸만 보내기 위해 필요하다) */
export type SubscriptionSaveTarget =
  | "new"
  | { id: number; before: SubscriptionFormValues };

/** 구독료 등록·수정. 성공하면 구독료 표와 요약을 다시 불러온 뒤 onSaved를 부른다. */
export function useSaveSubscription(
  target: SubscriptionSaveTarget,
  onSaved: () => void,
) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (values: SubscriptionFormValues) =>
      target === "new"
        ? createSubscription(subscriptionCreateBody(values))
        : updateSubscription(
            target.id,
            subscriptionUpdateBody(target.before, values),
          ),
    onSuccess: async () => {
      await Promise.all(
        SUBSCRIPTION_AFFECTED_KEYS.map((queryKey) =>
          queryClient.invalidateQueries({ queryKey }),
        ),
      );
      onSaved();
    },
  });
}
