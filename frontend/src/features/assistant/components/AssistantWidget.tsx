import { zodResolver } from "@hookform/resolvers/zod";
import { useQuery } from "@tanstack/react-query";
import {
  useEffect,
  useId,
  useRef,
  useState,
  useSyncExternalStore,
} from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { Button } from "../../../shared/components/ui/Button";
import { useAssistantBridge } from "../../../shared/lib/assistant";
import { assistantStatusOptions, sessionOptions } from "../api/assistant";
import { useAssistantChat } from "../hooks/useAssistantChat";
import {
  type AssistantPageContext,
  pageContextLabel,
} from "../lib/page-context";
import { AssistantLogin } from "./AssistantLogin";
import { AssistantMessages } from "./AssistantMessages";

const schema = z.object({
  message: z
    .string()
    .trim()
    .min(1, "요청을 입력해 주세요.")
    .max(1000, "1,000자 이내로 입력해 주세요."),
});
const noopSubscribe = () => () => {};
const emptySnapshot = () => null;

export function AssistantWidget({
  pageContext,
  onLogout,
  logoutPending,
  logoutError,
}: {
  pageContext?: AssistantPageContext;
  onLogout: () => void;
  logoutPending: boolean;
  logoutError?: string;
}) {
  const [open, setOpen] = useState(false);
  const panelId = useId();
  const launcher = useRef<HTMLButtonElement>(null);
  const heading = useRef<HTMLHeadingElement>(null);
  const bridge = useAssistantBridge();
  const target = useSyncExternalStore(
    bridge?.subscribe ?? noopSubscribe,
    bridge?.getSnapshot ?? emptySnapshot,
  );
  const session = useQuery({ ...sessionOptions, enabled: open });
  const status = useQuery({
    ...assistantStatusOptions,
    enabled: open && !!session.data,
  });
  const chat = useAssistantChat(
    session.data?.user_id ?? (session.isPending ? undefined : null),
    pageContext,
  );
  const form = useForm<z.infer<typeof schema>>({
    resolver: zodResolver(schema),
    defaultValues: { message: "" },
  });
  useEffect(() => {
    if (open) heading.current?.focus();
  }, [open]);
  const close = () => {
    setOpen(false);
    launcher.current?.focus();
  };
  return (
    <>
      <button
        ref={launcher}
        type="button"
        aria-label={open ? "AI 도우미 닫기" : "AI 도우미 열기"}
        aria-expanded={open}
        aria-controls={panelId}
        onClick={() => (open ? close() : setOpen(true))}
        className="fixed right-6 bottom-6 z-40 flex size-14 items-center justify-center rounded-full bg-brand text-body font-bold text-white shadow-lg transition-transform hover:scale-105 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand motion-reduce:transition-none"
      >
        AI
      </button>
      {open && (
        <section
          id={panelId}
          role="dialog"
          aria-labelledby={`${panelId}-title`}
          onKeyDown={(event) => {
            if (event.key === "Escape") {
              event.stopPropagation();
              close();
            }
          }}
          className="fixed right-6 bottom-24 z-40 flex h-160 max-h-[calc(100dvh-8rem)] w-100 flex-col overflow-hidden rounded-2xl border border-grey-200 bg-white text-grey-900 shadow-xl"
        >
          <header className="flex shrink-0 items-center justify-between gap-2 border-b border-grey-100 p-4">
            <h2
              ref={heading}
              tabIndex={-1}
              id={`${panelId}-title`}
              className="text-section font-bold outline-none"
            >
              AI 도우미
            </h2>
            <div className="flex items-center gap-1">
              {session.data && (
                <>
                  <Button
                    variant="secondary"
                    size="sm"
                    disabled={chat.busy}
                    onClick={chat.clear}
                  >
                    대화 지우기
                  </Button>
                  <Button
                    variant="secondary"
                    size="sm"
                    disabled={chat.busy || logoutPending}
                    onClick={onLogout}
                  >
                    로그아웃
                  </Button>
                </>
              )}
              <Button
                variant="secondary"
                size="sm"
                aria-label="채팅창 닫기"
                onClick={close}
              >
                ×
              </Button>
            </div>
          </header>
          {session.isPending || (session.isFetching && !!session.data) ? (
            <p role="status" className="p-5 text-body-sm">
              로그인 상태를 확인하고 있어요.
            </p>
          ) : session.isError && session.data !== null ? (
            <div className="space-y-3 p-5">
              <p role="alert" className="text-body-sm">
                로그인 상태를 확인하지 못했어요.
              </p>
              <Button
                variant="secondary"
                onClick={() => void session.refetch()}
              >
                다시 확인
              </Button>
            </div>
          ) : !session.data ? (
            <>
              <AssistantLogin />
              {session.isError && (
                <p role="alert" className="px-5 pb-5 text-body-sm text-red-600">
                  로그인 상태를 다시 확인하지 못했어요. 로그인하거나 잠시 후
                  다시 시도해 주세요.
                </p>
              )}
            </>
          ) : (
            <>
              <AssistantMessages
                messages={chat.messages}
                busy={chat.busy}
                onApply={chat.apply}
                onUndo={chat.undo}
                undoId={chat.undoId}
                inSimulator={!!target}
              />
              {status.isPending && (
                <p role="status" className="px-5 text-caption text-grey-600">
                  AI 연결 설정을 확인하고 있어요.
                </p>
              )}
              {status.isError && (
                <div className="px-5 text-caption text-red-600">
                  <p role="alert">AI 상태를 확인하지 못했어요.</p>
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={() => {
                      void session.refetch();
                      void status.refetch();
                    }}
                  >
                    다시 확인
                  </Button>
                </div>
              )}
              {status.data && !status.data.enabled && (
                <p role="status" className="px-5 text-body-sm text-grey-600">
                  AI 도우미가 비활성화되어 있어요. 관리자에게 문의해 주세요.
                </p>
              )}
              {(chat.error || logoutError) && (
                <p role="alert" className="px-5 py-2 text-body-sm text-red-600">
                  {chat.error || logoutError}
                </p>
              )}
              <form
                noValidate
                onSubmit={form.handleSubmit(async ({ message }) => {
                  if (await chat.send(message)) form.reset();
                })}
                className="shrink-0 space-y-2 border-t border-grey-100 p-4"
              >
                <label htmlFor={`${panelId}-message`} className="sr-only">
                  질문 또는 설정 요청
                </label>
                {pageContext && (
                  <p className="text-caption text-grey-600">
                    조회 기준: {pageContextLabel(pageContext)}
                  </p>
                )}
                <textarea
                  id={`${panelId}-message`}
                  {...form.register("message")}
                  onKeyDown={(event) => {
                    if (
                      event.key !== "Enter" ||
                      event.shiftKey ||
                      event.nativeEvent.isComposing ||
                      event.nativeEvent.keyCode === 229
                    )
                      return;
                    event.preventDefault();
                    if (event.repeat || chat.busy || !status.data?.enabled)
                      return;
                    event.currentTarget.form?.requestSubmit();
                  }}
                  rows={3}
                  maxLength={1000}
                  aria-describedby={`${panelId}-message-help`}
                  placeholder="조회하거나 바꿀 설정을 입력해 주세요"
                  disabled={chat.busy || !status.data?.enabled}
                  className="w-full resize-none rounded-control border border-grey-200 bg-grey-50 p-3 text-body-sm focus:outline-brand disabled:opacity-50"
                />
                {form.formState.errors.message && (
                  <p role="alert" className="text-caption text-red-600">
                    {form.formState.errors.message.message}
                  </p>
                )}
                <div className="flex items-center justify-between gap-3">
                  <p
                    id={`${panelId}-message-help`}
                    className="text-caption text-grey-600"
                  >
                    Enter로 전송 · Shift+Enter로 줄바꿈
                    <br />
                    새로고침하면 대화가 지워져요.
                  </p>
                  <Button
                    type="submit"
                    size="sm"
                    disabled={chat.busy || !status.data?.enabled}
                  >
                    보내기
                  </Button>
                </div>
              </form>
            </>
          )}
        </section>
      )}
    </>
  );
}
