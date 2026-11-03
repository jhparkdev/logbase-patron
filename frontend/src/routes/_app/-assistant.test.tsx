// @vitest-environment jsdom
import { focusManager } from "@tanstack/react-query";
import {
  act,
  createEvent,
  fireEvent,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import { afterEach, beforeAll, expect, test, vi } from "vitest";
import { sessionOptions } from "../../features/assistant/api/assistant";
import { renderAt } from "../../test/renderAt";
import {
  ACTIVE_MODEL,
  EXECUTION_PROVIDERS,
  HISTORY_LIST,
  RERUN_DRAFT,
  RUN_DETAIL,
  RUN_ID,
  SCENARIOS,
} from "../../test/simulationHistoryApi";

beforeAll(() => {
  window.scrollTo = vi.fn();
  HTMLDialogElement.prototype.showModal = function () {
    this.setAttribute("open", "");
  };
  HTMLDialogElement.prototype.close = function () {
    this.removeAttribute("open");
  };
});
afterEach(() => {
  focusManager.setFocused(undefined);
  vi.unstubAllGlobals();
});
const headers = { "Content-Type": "application/json" };
const user = {
  user_id: 1,
  user_code: "U-1",
  name: "테스터",
  email: "test@example.com",
};
const response = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers });

function stub(chat: (request: Request) => Promise<Response>, loggedIn = true) {
  const requests: Request[] = [];
  vi.stubGlobal("fetch", async (request: Request) => {
    requests.push(request.clone());
    const path = new URL(request.url).pathname;
    if (path === "/api/auth/me")
      return loggedIn
        ? response(user)
        : response(
            { code: "UNAUTHENTICATED", message: "로그인이 필요합니다." },
            401,
          );
    if (path === "/api/assistant/status")
      return response({ enabled: true, model: "qwen3.5:4b" });
    if (path === "/api/assistant/chat") return chat(request);
    if (path === "/api/assistant/settings/validate")
      return response((await request.json()).patch);
    if (path === "/api/auth/logout") {
      loggedIn = false;
      return new Response(null, { status: 204 });
    }
    if (path === "/api/models")
      return response({
        items: [ACTIVE_MODEL],
        page: 1,
        page_size: 100,
        total: 1,
      });
    if (path.endsWith("/execution-providers"))
      return response(EXECUTION_PROVIDERS);
    if (path === "/api/scenarios") return response(SCENARIOS);
    if (path === "/api/simulations/images/limits")
      return response({
        max_count: 4,
        max_bytes: 5242880,
        mime_types: ["image/png"],
      });
    return response({ items: [], total: 0 });
  });
  return requests;
}

async function openChat() {
  fireEvent.click(
    await screen.findByRole("button", { name: "AI 도우미 열기" }),
  );
  await waitFor(() =>
    expect(
      screen.getByRole("button", { name: "보내기" }).hasAttribute("disabled"),
    ).toBe(false),
  );
}

async function send() {
  fireEvent.change(screen.getByLabelText("질문 또는 설정 요청"), {
    target: { value: "토큰만 바꿔줘" },
  });
  fireEvent.click(screen.getByRole("button", { name: "보내기" }));
}

test.each(["history", "simulation"])(
  "a %s source with a run ID opens its existing P05 detail modal",
  async (kind) => {
    stub(async () =>
      response({
        message: "조회한 실행 정보예요.",
        sources: [
          {
            title: "실행 상세",
            kind,
            simulation_id: RUN_ID,
            requested_at: RUN_DETAIL.summary.requested_at,
          },
        ],
      }),
    );
    const originalFetch = fetch;
    const detailCalls: string[] = [];
    vi.stubGlobal("fetch", (request: Request) => {
      const path = new URL(request.url).pathname;
      if (path === "/api/simulations")
        return Promise.resolve(response({ items: [], total: 0 }));
      if (path === `/api/simulations/${RUN_ID}`) {
        detailCalls.push(path);
        return Promise.resolve(response(RUN_DETAIL));
      }
      if (path === `/api/simulations/${RUN_ID}/rerun-draft`)
        return Promise.resolve(response(RERUN_DRAFT));
      return originalFetch(request);
    });
    const router = renderAt("/models");
    await openChat();
    await send();
    fireEvent.click(
      await screen.findByRole("link", {
        name: "실행 상세 · 2026-10-22 10:00:00",
      }),
    );
    const dialog = await screen.findByRole("dialog", {
      name: "시뮬레이션 실행 상세",
    });
    expect(await within(dialog).findByText("과거 Prompt 원문")).toBeTruthy();
    expect(within(dialog).getByText("모델 응답 원문")).toBeTruthy();
    expect(router.state.location.pathname).toBe("/simulation-history");
    expect(router.state.location.search).toMatchObject({
      selected: RUN_ID,
      detail: true,
    });
    expect(detailCalls).toEqual([`/api/simulations/${RUN_ID}`]);
    fireEvent.click(within(dialog).getByRole("button", { name: "창 닫기" }));
    await waitFor(() =>
      expect(router.state.location.search).toMatchObject({
        selected: RUN_ID,
        detail: false,
      }),
    );
    expect(screen.getByText("조건에 맞는 실행 이력이 없어요")).toBeTruthy();
  },
);

test("a history overview without an ID opens P05 without selecting an arbitrary run", async () => {
  stub(async () =>
    response({
      message: "최근 이력이에요.",
      sources: [{ title: "시뮬레이션 이력", kind: "history" }],
    }),
  );
  const originalFetch = fetch;
  vi.stubGlobal("fetch", (request: Request) =>
    new URL(request.url).pathname === "/api/simulations"
      ? Promise.resolve(response(HISTORY_LIST))
      : originalFetch(request),
  );
  const router = renderAt("/models");
  await openChat();
  await send();
  fireEvent.click(await screen.findByRole("link", { name: "시뮬레이션 이력" }));
  await screen.findByRole("button", { name: RUN_ID });
  expect(router.state.location.pathname).toBe("/simulation-history");
  expect(router.state.location.search).toMatchObject({ detail: false });
  expect(
    screen.queryByRole("dialog", { name: "시뮬레이션 실행 상세" }),
  ).toBeNull();
});

test.each([
  ["최근 요청 시각을 알려줘", "2026년 11월 2일 16:11:38 (한국시간)"],
  ["최근 요청 시각을 ISO 원문으로 알려줘", "2026-11-02T07:11:38.580827Z"],
])(
  "answer formatting follows the request while keeping conversation data intact: %s",
  async (question, displayed) => {
    const original = "최근 시각: **2026-11-02T07:11:38.580827Z**";
    const requests = stub(async () => response({ message: original }));
    renderAt("/simulator");
    await openChat();
    const input = screen.getByLabelText("질문 또는 설정 요청");
    fireEvent.change(input, { target: { value: question } });
    fireEvent.keyDown(input, { key: "Enter" });
    await screen.findByText(displayed);
    await waitFor(() => expect((input as HTMLTextAreaElement).value).toBe(""));
    await send();
    await waitFor(() =>
      expect(
        requests.filter(
          (request) => new URL(request.url).pathname === "/api/assistant/chat",
        ),
      ).toHaveLength(2),
    );
    const calls = requests.filter(
      (request) => new URL(request.url).pathname === "/api/assistant/chat",
    );
    expect((await calls[1].json()).messages).toContainEqual({
      role: "assistant",
      content: original,
    });
  },
);

test("Enter sends once through the chat form and clears input after success", async () => {
  let finish: ((value: Response) => void) | undefined;
  const requests = stub(
    async () =>
      new Promise<Response>((resolve) => {
        finish = resolve;
      }),
  );
  renderAt("/simulator");
  await openChat();
  const input = screen.getByLabelText(
    "질문 또는 설정 요청",
  ) as HTMLTextAreaElement;
  fireEvent.change(input, { target: { value: "등록 모델을 알려줘" } });
  fireEvent.keyDown(input, { key: "Enter" });
  await waitFor(() => expect(finish).toBeDefined());
  fireEvent.keyDown(input, { key: "Enter" });
  expect(
    requests.filter(
      (request) => new URL(request.url).pathname === "/api/assistant/chat",
    ),
  ).toHaveLength(1);
  await act(async () => {
    finish?.(response({ message: "모델 조회 완료" }));
  });
  await screen.findByText("모델 조회 완료");
  await waitFor(() => expect(input.value).toBe(""));
});

test("Shift+Enter allows a newline and Enter sends the multiline message", async () => {
  const requests = stub(async () => response({ message: "여러 줄 요청 확인" }));
  renderAt("/simulator");
  await openChat();
  const input = screen.getByLabelText("질문 또는 설정 요청");
  fireEvent.change(input, { target: { value: "첫 번째 줄" } });
  const newline = createEvent.keyDown(input, { key: "Enter", shiftKey: true });
  fireEvent(input, newline);
  expect(newline.defaultPrevented).toBe(false);
  expect(
    requests.some(
      (request) => new URL(request.url).pathname === "/api/assistant/chat",
    ),
  ).toBe(false);
  // jsdom은 키 기본 동작으로 텍스트를 삽입하지 않아 실제 줄바꿈 결과를 입력한다.
  fireEvent.change(input, { target: { value: "첫 번째 줄\n두 번째 줄" } });
  fireEvent.keyDown(input, { key: "Enter" });
  await screen.findByText("여러 줄 요청 확인");
  const request = requests.find(
    (item) => new URL(item.url).pathname === "/api/assistant/chat",
  );
  if (!request) throw new Error("Chat request missing");
  expect((await request.json()).messages.at(-1).content).toBe(
    "첫 번째 줄\n두 번째 줄",
  );
});

test.each([{ isComposing: true }, { keyCode: 229 }])(
  "Enter used to confirm IME composition does not send (%j)",
  async (composition) => {
    const requests = stub(async () =>
      response({ message: "조합 후 전송 완료" }),
    );
    renderAt("/simulator");
    await openChat();
    const input = screen.getByLabelText(
      "질문 또는 설정 요청",
    ) as HTMLTextAreaElement;
    fireEvent.change(input, { target: { value: "한글 입력" } });
    const confirm = createEvent.keyDown(input, {
      key: "Enter",
      ...composition,
    });
    fireEvent(input, confirm);
    expect(confirm.defaultPrevented).toBe(false);
    expect(
      requests.some(
        (request) => new URL(request.url).pathname === "/api/assistant/chat",
      ),
    ).toBe(false);
    expect(input.value).toBe("한글 입력");
    fireEvent.keyDown(input, { key: "Enter" });
    await screen.findByText("조합 후 전송 완료");
  },
);

test("Enter validates blank input and held Enter does not submit a message", async () => {
  const requests = stub(async () => response({ message: "정상 전송 완료" }));
  renderAt("/simulator");
  await openChat();
  const input = screen.getByLabelText("질문 또는 설정 요청");
  fireEvent.change(input, { target: { value: "   " } });
  fireEvent.keyDown(input, { key: "Enter" });
  await screen.findByText("요청을 입력해 주세요.");
  fireEvent.change(input, { target: { value: "새 질문" } });
  fireEvent.keyDown(input, { key: "Enter", repeat: true });
  expect(
    requests.some(
      (request) => new URL(request.url).pathname === "/api/assistant/chat",
    ),
  ).toBe(false);
  fireEvent.keyDown(input, { key: "Enter" });
  await screen.findByText("정상 전송 완료");
});

test("applies only requested settings, supports undo and never starts a paid simulation", async () => {
  const requests = stub(async () =>
    response({
      message: "설정을 준비했어요.",
      patch: { execution_config: { max_tokens: 2048 } },
      sources: [],
    }),
  );
  renderAt("/simulator");
  const prompt = await screen.findByLabelText("Prompt");
  fireEvent.change(prompt, { target: { value: "유지할 프롬프트" } });
  await openChat();
  await send();
  await screen.findByText(
    "시뮬레이터에 설정을 반영했어요. 실행 전 입력값을 확인해 주세요.",
  );
  expect(
    (screen.getByLabelText("공통 최대 출력 토큰") as HTMLInputElement).value,
  ).toBe("2048");
  expect((prompt as HTMLTextAreaElement).value).toBe("유지할 프롬프트");
  fireEvent.click(screen.getByRole("button", { name: "설정 되돌리기" }));
  await screen.findByText("설정 변경을 되돌렸어요.");
  expect(
    (screen.getByLabelText("공통 최대 출력 토큰") as HTMLInputElement).value,
  ).toBe("");
  expect(
    requests.some(
      (request) =>
        request.method === "POST" &&
        new URL(request.url).pathname === "/api/simulations",
    ),
  ).toBe(false);
});

test("late model responses cannot overwrite a user's intervening edits", async () => {
  let finish: ((value: Response) => void) | undefined;
  stub(
    async () =>
      new Promise<Response>((resolve) => {
        finish = resolve;
      }),
  );
  renderAt("/simulator");
  const prompt = await screen.findByLabelText("Prompt");
  await openChat();
  await send();
  await waitFor(() => expect(finish).toBeDefined());
  fireEvent.change(prompt, { target: { value: "새로 수정한 입력" } });
  await act(async () =>
    finish?.(
      response({
        message: "설정 초안",
        patch: { prompt_text: "덮어쓰면 안 됨" },
      }),
    ),
  );
  await screen.findByText(/요청 후 입력값이 바뀌어/);
  expect((prompt as HTMLTextAreaElement).value).toBe("새로 수정한 입력");
});

test("conversation survives close and route navigation until explicitly cleared", async () => {
  stub(async () => response({ message: "대화 유지 확인", sources: [] }));
  const router = renderAt("/simulator");
  await openChat();
  await send();
  await screen.findByText("대화 유지 확인");
  fireEvent.click(screen.getByRole("button", { name: "채팅창 닫기" }));
  await act(async () => {
    await router.navigate({ to: "/models" });
  });
  await openChat();
  expect(screen.getByText("대화 유지 확인")).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "대화 지우기" }));
  expect(screen.queryByText("대화 유지 확인")).toBeNull();
});

test("unauthenticated users see login and never call the agent", async () => {
  const requests = stub(async () => {
    throw new Error("must not call");
  }, false);
  renderAt("/simulator");
  fireEvent.click(
    await screen.findByRole("button", { name: "AI 도우미 열기" }),
  );
  expect(await screen.findByLabelText("비밀번호")).toBeTruthy();
  expect(screen.queryByRole("button", { name: "보내기" })).toBeNull();
  expect(
    requests.some((request) =>
      new URL(request.url).pathname.startsWith("/api/assistant/"),
    ),
  ).toBe(false);
});

test.each([401, 503])(
  "login inputs survive a window-focus session check returning %i",
  async (status) => {
    stub(async () => response({ message: "unused" }), false);
    const originalFetch = fetch;
    let finish: ((value: Response) => void) | undefined;
    let sessionChecks = 0;
    vi.stubGlobal("fetch", (request: Request) => {
      if (new URL(request.url).pathname === "/api/auth/me") {
        sessionChecks += 1;
        if (sessionChecks > 1)
          return new Promise<Response>((resolve) => {
            finish = resolve;
          });
      }
      return originalFetch(request);
    });
    renderAt("/simulator");
    fireEvent.click(
      await screen.findByRole("button", { name: "AI 도우미 열기" }),
    );
    const email = (await screen.findByLabelText("이메일")) as HTMLInputElement;
    const password = screen.getByLabelText("비밀번호") as HTMLInputElement;
    fireEvent.change(email, { target: { value: "draft@example.test" } });
    fireEvent.change(password, {
      target: { value: "temporary-test-password" },
    });

    await act(async () => {
      focusManager.setFocused(false);
      focusManager.setFocused(true);
    });
    await waitFor(() => expect(finish).toBeDefined());
    expect(screen.queryByLabelText("이메일")).toBe(email);
    expect(screen.queryByLabelText("비밀번호")).toBe(password);
    await act(async () => {
      finish?.(response({ code: "BAD_REQUEST", message: "확인 실패" }, status));
    });
    expect((await screen.findByLabelText("이메일")) as HTMLInputElement).toBe(
      email,
    );
    expect(email.value).toBe("draft@example.test");
    expect(password.value).toBe("temporary-test-password");
  },
);

test("an earlier focus check cannot undo a successful login", async () => {
  stub(async () => response({ message: "unused" }), false);
  const originalFetch = fetch;
  let finish: ((value: Response) => void) | undefined;
  let sessionChecks = 0;
  vi.stubGlobal("fetch", (request: Request) => {
    const path = new URL(request.url).pathname;
    if (path === "/api/auth/login") return Promise.resolve(response(user));
    if (path === "/api/auth/me" && ++sessionChecks > 1)
      return new Promise<Response>((resolve) => {
        finish = resolve;
      });
    return originalFetch(request);
  });
  const router = renderAt("/simulator");
  fireEvent.click(
    await screen.findByRole("button", { name: "AI 도우미 열기" }),
  );
  fireEvent.change(await screen.findByLabelText("이메일"), {
    target: { value: "draft@example.test" },
  });
  fireEvent.change(screen.getByLabelText("비밀번호"), {
    target: { value: "temporary-test-password" },
  });
  await act(async () => {
    focusManager.setFocused(false);
    focusManager.setFocused(true);
  });
  await waitFor(() => expect(finish).toBeDefined());
  fireEvent.click(screen.getByRole("button", { name: "로그인" }));
  await screen.findByRole("button", { name: "보내기" });
  await act(async () => {
    finish?.(
      response({ code: "UNAUTHENTICATED", message: "로그인 필요" }, 401),
    );
  });
  expect(
    router.options.context.queryClient.getQueryData(sessionOptions.queryKey),
  ).toEqual(user);
  expect(screen.queryByLabelText("비밀번호")).toBeNull();
});

test("focus revalidation still hides authenticated chat and clears expired sessions", async () => {
  stub(async () => response({ message: "이전 세션의 대화" }));
  const originalFetch = fetch;
  let finish: ((value: Response) => void) | undefined;
  let sessionChecks = 0;
  vi.stubGlobal("fetch", (request: Request) => {
    if (new URL(request.url).pathname === "/api/auth/me" && ++sessionChecks > 1)
      return new Promise<Response>((resolve) => {
        finish = resolve;
      });
    return originalFetch(request);
  });
  renderAt("/simulator");
  await openChat();
  await send();
  await screen.findByText("이전 세션의 대화");
  await act(async () => {
    focusManager.setFocused(false);
    focusManager.setFocused(true);
  });
  await waitFor(() => expect(finish).toBeDefined());
  await screen.findByText("로그인 상태를 확인하고 있어요.");
  expect(screen.queryByText("이전 세션의 대화")).toBeNull();
  await act(async () => {
    finish?.(
      response({ code: "UNAUTHENTICATED", message: "로그인 필요" }, 401),
    );
  });
  await screen.findByLabelText("비밀번호");
  expect(screen.queryByText("이전 세션의 대화")).toBeNull();
});

test("a patch prepared on another screen is revalidated against P04 before applying", async () => {
  const requests = stub(async () =>
    response({
      message: "설정을 준비했어요.",
      patch: { execution_config: { max_tokens: 1024 } },
      sources: [],
    }),
  );
  const router = renderAt("/models");
  await openChat();
  await send();
  await screen.findByRole("link", { name: "시뮬레이터 열기" });
  await act(async () => {
    await router.navigate({
      to: "/simulator",
      search: { sort: "model", direction: "asc" },
    });
  });
  fireEvent.click(await screen.findByRole("button", { name: "설정 적용" }));
  await screen.findByText("시뮬레이터에 설정을 반영했어요.");
  expect(
    (screen.getByLabelText("공통 최대 출력 토큰") as HTMLInputElement).value,
  ).toBe("1024");
  expect(
    requests.some(
      (request) =>
        new URL(request.url).pathname === "/api/assistant/settings/validate",
    ),
  ).toBe(true);
});

test("logout clears the conversation and later reopen requires login", async () => {
  stub(async () =>
    response({ message: "로그아웃 후 사라질 대화", sources: [] }),
  );
  renderAt("/simulator");
  await openChat();
  await send();
  await screen.findByText("로그아웃 후 사라질 대화");
  fireEvent.click(screen.getByRole("button", { name: "로그아웃" }));
  await screen.findByLabelText("비밀번호");
  expect(screen.queryByText("로그아웃 후 사라질 대화")).toBeNull();
  fireEvent.click(screen.getByRole("button", { name: "채팅창 닫기" }));
  fireEvent.click(screen.getByRole("button", { name: "AI 도우미 열기" }));
  expect(await screen.findByLabelText("비밀번호")).toBeTruthy();
});
