import { Link } from "@tanstack/react-router";
import { useEffect, useRef } from "react";
import { Button } from "../../../shared/components/ui/Button";
import type { ChatMessage } from "../lib/conversation";
import { AssistantMessageContent } from "./AssistantMessageContent";
import { AssistantSourceLink } from "./AssistantSourceLink";

export function AssistantMessages({
  messages,
  busy,
  onApply,
  onUndo,
  undoId,
  inSimulator,
}: {
  messages: ChatMessage[];
  busy: boolean;
  onApply: (id: string) => void;
  onUndo: () => void;
  undoId?: string;
  inSimulator: boolean;
}) {
  const transcript = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (transcript.current)
      transcript.current.scrollTop =
        messages.length || busy ? transcript.current.scrollHeight : 0;
  }, [messages.length, busy]);
  return (
    <div
      ref={transcript}
      role="log"
      aria-label="AI 도우미 대화"
      aria-live="polite"
      className="min-h-0 flex-1 space-y-4 overflow-y-auto p-5"
    >
      {!messages.length && (
        <div className="space-y-3 text-body-sm text-grey-600">
          <p className="font-semibold text-grey-900">
            어떤 작업을 도와드릴까요?
          </p>
          <p>
            고객·내부 사용량과 비용, 모델·시뮬레이션 이력을 조회하거나 비교
            설정을 준비할 수 있어요.
          </p>
          <p className="rounded-lg bg-grey-50 p-3">
            “현재 선택할 수 있는 모델을 알려줘”
            <br />
            “최대 출력 토큰만 2,048로 바꿔줘”
          </p>
        </div>
      )}
      {messages.map((message) => (
        <article
          key={message.id}
          aria-label={message.role === "user" ? "내 메시지" : "AI 답변"}
          className={`rounded-2xl p-3 text-body-sm ${message.role === "user" ? "ml-8 bg-blue-50" : "mr-2 bg-grey-50"}`}
        >
          {message.role === "assistant" ? (
            <AssistantMessageContent
              content={message.content}
              rawValues={message.showRawValues}
            />
          ) : (
            <p className="whitespace-pre-wrap wrap-anywhere">
              {message.content}
            </p>
          )}
          {!!message.sources?.length && (
            <div className="mt-3 flex flex-wrap gap-3 text-caption text-blue-600">
              {message.sources.map((source) => (
                <AssistantSourceLink
                  key={`${source.kind}:${source.simulation_id ?? ""}:${JSON.stringify(source.page_context)}:${source.page_number ?? ""}:${source.page_size ?? ""}:${source.sort_key ?? ""}:${source.sort_order ?? ""}`}
                  source={source}
                />
              ))}
            </div>
          )}
          {message.patchState === "pending" && (
            <div className="mt-3 space-y-2">
              <p className="text-caption text-grey-600">
                설정을 준비했어요. 적용해도 비교 실행은 시작되지 않아요.
              </p>
              {inSimulator ? (
                <Button
                  variant="secondary"
                  size="sm"
                  disabled={busy}
                  onClick={() => onApply(message.id)}
                >
                  설정 적용
                </Button>
              ) : (
                <Link
                  to="/simulator"
                  search={{ sort: "model", direction: "asc" }}
                  className="text-label font-semibold text-blue-600 underline"
                >
                  시뮬레이터 열기
                </Link>
              )}
            </div>
          )}
          {message.notice && (
            <p role="status" className="mt-3 text-caption text-grey-600">
              {message.notice}
            </p>
          )}
          {message.patchState === "applied" && undoId === message.id && (
            <Button
              variant="secondary"
              size="sm"
              className="mt-2"
              disabled={busy}
              onClick={onUndo}
            >
              설정 되돌리기
            </Button>
          )}
        </article>
      ))}
      {busy && (
        <p role="status" className="text-body-sm text-grey-600">
          요청을 처리하고 있어요…
        </p>
      )}
    </div>
  );
}
