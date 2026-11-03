import { useMutation, useQueryClient } from "@tanstack/react-query";
import {
  createProject,
  createSubscription,
  PROJECT_OPTION_KEYS,
  SUBSCRIPTION_AFFECTED_KEYS,
  type SubscriptionProject,
  updateSubscription,
} from "../api/budget";
import {
  type SubscriptionFormValues,
  subscriptionCreateBody,
  subscriptionUpdateBody,
} from "../lib/forms";
import { resolveProject } from "../lib/newProject";

/** 등록("new") 또는 수정(번호와 수정 전 값. 바꾼 칸만 보내기 위해 필요하다) */
export type SubscriptionSaveTarget =
  | "new"
  | { id: number; before: SubscriptionFormValues };

/**
 * 구독료 등록·수정. 새 프로젝트를 적었으면 먼저 만들고(또는 같은 이름을 찾고) 그 번호로 저장한다.
 * 성공하면 구독료 표와 요약을, 프로젝트를 만들었으면 선택지도 다시 불러온 뒤 onSaved를 부른다.
 */
export function useSaveSubscription(
  target: SubscriptionSaveTarget,
  projects: SubscriptionProject[],
  onSaved: () => void,
) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (values: SubscriptionFormValues) => {
      const resolved = resolveProject(values, projects);
      const created = "createName" in resolved;
      const projectId = created
        ? (await createProject(resolved.createName)).project_id
        : resolved.projectId;
      if (target !== "new") {
        await updateSubscription(
          target.id,
          subscriptionUpdateBody(target.before, values, projectId),
        );
      } else if (projectId === null) {
        // 등록 폼은 subscriptionCreateSchema로 프로젝트를 반드시 받으므로 여기 오지 않는다. 타입을 좁히기 위한 것이다.
        throw new Error("귀속 프로젝트를 골라 주세요.");
      } else {
        await createSubscription(subscriptionCreateBody(values, projectId));
      }
      return created;
    },
    onSuccess: async (created) => {
      const keys = created
        ? [...SUBSCRIPTION_AFFECTED_KEYS, ...PROJECT_OPTION_KEYS]
        : SUBSCRIPTION_AFFECTED_KEYS;
      await Promise.all(
        keys.map((queryKey) => queryClient.invalidateQueries({ queryKey })),
      );
      onSaved();
    },
  });
}
