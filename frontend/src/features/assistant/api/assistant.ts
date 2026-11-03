import { queryOptions } from "@tanstack/react-query";
import { api, unwrap } from "../../../shared/api/client";
import type { components } from "../../../shared/api/schema";

type Schemas = components["schemas"];
export function assistantStatusOptions(userId: number) {
  return queryOptions({
    queryKey: ["assistant", "status", userId],
    queryFn: async ({ signal }) =>
      unwrap(await api.GET("/api/assistant/status", { signal })),
    retry: false,
    staleTime: 0,
  });
}

export async function chatAssistant(
  body: Schemas["AssistantChatRequest"],
  signal: AbortSignal,
) {
  return unwrap(await api.POST("/api/assistant/chat", { body, signal }));
}

export async function validateAssistantSettings(
  body: Schemas["AssistantSettingsRequest"],
  signal: AbortSignal,
) {
  return unwrap(
    await api.POST("/api/assistant/settings/validate", { body, signal }),
  );
}
