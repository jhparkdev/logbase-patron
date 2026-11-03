import { queryOptions } from "@tanstack/react-query";
import { ApiError, api, unwrap } from "../../../shared/api/client";
import type { components } from "../../../shared/api/schema";

type Schemas = components["schemas"];
export const sessionOptions = queryOptions({
  queryKey: ["assistant", "session"],
  queryFn: async () => {
    try {
      return unwrap(await api.GET("/api/auth/me"));
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) return null;
      throw error;
    }
  },
  retry: false,
  staleTime: 0,
});

export const assistantStatusOptions = queryOptions({
  queryKey: ["assistant", "status"],
  queryFn: async () => unwrap(await api.GET("/api/assistant/status")),
  retry: false,
  staleTime: 0,
});

export async function loginAssistant(body: Schemas["LoginRequest"]) {
  return unwrap(await api.POST("/api/auth/login", { body }));
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
