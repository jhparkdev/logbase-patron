import { useMutation } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { ApiError } from "../../../shared/api/client";
import {
  type SimulatorSnapshot,
  useAssistantBridge,
} from "../../../shared/lib/assistant";
import { chatAssistant, validateAssistantSettings } from "../api/assistant";
import { type ChatMessage, requestMessages } from "../lib/conversation";
import { requestsRawValues } from "../lib/message-content";
import type { AssistantPageContext } from "../lib/page-context";

export function useAssistantChat(
  onSessionExpired: () => void,
  pageContext?: AssistantPageContext,
) {
  const bridge = useAssistantBridge();
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [error, setError] = useState("");
  const [undoId, setUndoId] = useState<string>();
  const controller = useRef<AbortController | null>(null);
  const mutation = useMutation({
    mutationFn: ({
      body,
      signal,
    }: {
      body: Parameters<typeof chatAssistant>[0];
      signal: AbortSignal;
    }) => chatAssistant(body, signal),
    retry: false,
    gcTime: 0,
  });
  const { reset: resetMutation } = mutation;
  const validation = useMutation({
    mutationFn: ({
      body,
      signal,
    }: {
      body: Parameters<typeof validateAssistantSettings>[0];
      signal: AbortSignal;
    }) => validateAssistantSettings(body, signal),
    retry: false,
    gcTime: 0,
  });
  const { reset: resetValidation } = validation;
  useEffect(() => () => controller.current?.abort(), []);

  const send = async (content: string) => {
    if (mutation.isPending || validation.isPending || !content.trim())
      return false;
    const target = bridge?.getSnapshot();
    let snapshot: SimulatorSnapshot | undefined;
    try {
      snapshot = target?.read();
    } catch {
      setError("시뮬레이터 입력값을 확인한 뒤 다시 요청해 주세요.");
      return false;
    }
    const abort = new AbortController();
    controller.current = abort;
    const id = crypto.randomUUID();
    const body = {
      messages: requestMessages(messages, content),
      simulator: snapshot?.state,
      page_context: pageContext,
    };
    setMessages((previous) => [...previous, { id, role: "user", content }]);
    setError("");
    try {
      const result = await mutation.mutateAsync({ body, signal: abort.signal });
      if (abort.signal.aborted || controller.current !== abort) return false;
      const message: ChatMessage = {
        id: crypto.randomUUID(),
        role: "assistant",
        content: result.message,
        sources: result.sources,
        patch: result.patch,
        patchState: result.patch ? "pending" : undefined,
        showRawValues: requestsRawValues(content),
      };
      if (result.patch && target && snapshot) {
        const notice =
          bridge?.getSnapshot() !== target
            ? "요청 중 화면 상태가 바뀌어 설정을 적용하지 않았어요. 다시 요청해 주세요."
            : target.apply(result.patch, snapshot.revision);
        message.patchState = notice ? "rejected" : "applied";
        message.notice =
          notice ??
          "시뮬레이터에 설정을 반영했어요. 실행 전 입력값을 확인해 주세요.";
        if (!notice) setUndoId(message.id);
      }
      setMessages((previous) => [...previous, message].slice(-40));
      return true;
    } catch (failure) {
      if (abort.signal.aborted) return false;
      if (failure instanceof ApiError && failure.status === 401) {
        onSessionExpired();
        return false;
      }
      setMessages((previous) =>
        previous.filter((message) => message.id !== id),
      );
      setError(
        failure instanceof ApiError
          ? failure.message
          : "응답을 받지 못했어요. 다시 시도해 주세요.",
      );
      return false;
    }
  };

  const apply = async (id: string) => {
    if (mutation.isPending || validation.isPending) return;
    const message = messages.find((item) => item.id === id);
    const target = bridge?.getSnapshot();
    if (!message?.patch || !target) {
      setError("시뮬레이터 화면을 연 뒤 설정을 적용해 주세요.");
      return;
    }
    let notice: string | undefined;
    const abort = new AbortController();
    controller.current = abort;
    try {
      const snapshot = target.read();
      const patch = await validation.mutateAsync({
        body: { simulator: snapshot.state, patch: message.patch },
        signal: abort.signal,
      });
      if (abort.signal.aborted || controller.current !== abort) return;
      notice =
        bridge?.getSnapshot() !== target
          ? "화면 상태가 바뀌어 적용하지 않았어요. 다시 요청해 주세요."
          : target.apply(patch, snapshot.revision);
    } catch (failure) {
      if (abort.signal.aborted) return;
      if (failure instanceof ApiError && failure.status === 401) {
        onSessionExpired();
        return;
      }
      notice =
        failure instanceof ApiError
          ? failure.message
          : "현재 입력값을 확인한 뒤 다시 요청해 주세요.";
    }
    setMessages((previous) =>
      previous.map((item) =>
        item.id === id
          ? {
              ...item,
              patchState: notice ? "rejected" : "applied",
              notice: notice ?? "시뮬레이터에 설정을 반영했어요.",
            }
          : item,
      ),
    );
    if (!notice) setUndoId(id);
  };

  const undo = () => {
    const target = bridge?.getSnapshot();
    const notice = target
      ? target.undo()
      : "시뮬레이터 화면에서 되돌려 주세요.";
    if (notice) {
      setError(notice);
      return;
    }
    setMessages((previous) =>
      previous.map((item) =>
        item.id === undoId
          ? { ...item, patchState: "undone", notice: "설정 변경을 되돌렸어요." }
          : item,
      ),
    );
    setUndoId(undefined);
  };

  return {
    messages,
    error,
    busy: mutation.isPending || validation.isPending,
    send,
    apply,
    undo,
    undoId,
    clear: () => {
      controller.current?.abort();
      controller.current = null;
      setMessages([]);
      setError("");
      setUndoId(undefined);
      resetMutation();
      resetValidation();
    },
  };
}
