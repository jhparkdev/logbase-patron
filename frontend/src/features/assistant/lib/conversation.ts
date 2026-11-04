import type { components } from "../../../shared/api/schema";

type Schemas = components["schemas"];
export type ChatMessage = Schemas["AssistantMessage"] & {
  id: string;
  sources?: Schemas["AssistantSource"][];
  patch?: Schemas["SimulatorPatch"] | null;
  patchState?: "pending" | "applied" | "rejected" | "undone";
  notice?: string;
  showRawValues?: boolean;
};

export function requestMessages(
  messages: ChatMessage[],
  content: string,
): Schemas["AssistantMessage"][] {
  const next = [...messages, { role: "user" as const, content }];
  const chosen: Schemas["AssistantMessage"][] = [];
  let remaining = 8000;
  for (const message of next.slice(-12).reverse()) {
    if (message.content.length > remaining) break;
    chosen.unshift({ role: message.role, content: message.content });
    remaining -= message.content.length;
  }
  return chosen;
}
