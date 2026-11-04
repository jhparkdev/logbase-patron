// @vitest-environment jsdom
import { act, fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import { currentUserQueryOptions } from "../features/auth/api/auth";
import { renderAt, TEST_USER } from "../test/renderAt";

afterEach(() => vi.unstubAllGlobals());

function jsonResponse(status: number, body: unknown) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

/** 로그인 요청에 대한 서버 응답을 정해 둔다. 그 밖의 요청은 테스트가 실패하도록 거절한다. */
function stubLoginResponse(status: number, body: unknown) {
  // openapi-fetch는 Request 객체 하나로 fetch를 부른다. 본문은 뒤에서 읽을 수 있게 여기서 건드리지 않는다.
  const fetchMock = vi.fn(async (request: Request) => {
    const { pathname } = new URL(request.url);
    if (pathname === "/api/auth/login" && request.method === "POST") {
      return jsonResponse(status, body);
    }
    throw new Error(`예상하지 않은 요청: ${request.method} ${pathname}`);
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

async function fillAndSubmit(email: string, password: string) {
  fireEvent.change(await screen.findByLabelText("이메일"), {
    target: { value: email },
  });
  fireEvent.change(screen.getByLabelText("비밀번호"), {
    target: { value: password },
  });
  fireEvent.click(screen.getByRole("button", { name: "로그인하기" }));
}

test("로그인 전에 시작한 세션 확인이 늦게 끝나도 새 로그인 상태를 덮어쓰지 않는다", async () => {
  stubLoginResponse(200, TEST_USER);
  const originalFetch = fetch;
  let finish: ((value: Response) => void) | undefined;
  vi.stubGlobal("fetch", (request: Request) => {
    const path = new URL(request.url).pathname;
    if (path === "/api/auth/me")
      return new Promise<Response>((resolve) => {
        finish = resolve;
      });
    if (path === "/api/models")
      return Promise.resolve(
        jsonResponse(200, { items: [], total: 0, page: 1, page_size: 10 }),
      );
    return originalFetch(request);
  });
  const router = renderAt("/login?redirect=%2Fmodels", { user: null });
  await screen.findByRole("heading", { level: 1, name: "로그인" });
  const queryClient = router.options.context.queryClient;
  const pending = queryClient
    .fetchQuery({ ...currentUserQueryOptions, staleTime: 0 })
    .catch(() => undefined);
  await waitFor(() => expect(finish).toBeDefined());
  await fillAndSubmit("admin1@patron.dev", "secret");
  await screen.findByRole("heading", { level: 1, name: "AI 모델 관리" });
  await act(async () => {
    finish?.(
      jsonResponse(401, { code: "UNAUTHENTICATED", message: "로그인 필요" }),
    );
    await pending;
  });
  expect(queryClient.getQueryData(currentUserQueryOptions.queryKey)).toEqual(
    TEST_USER,
  );
  expect(router.state.location.pathname).toBe("/models");
});

test("로그인하지 않은 상태로 보호된 화면에 들어가면 로그인 화면으로 보내고 원래 주소를 남긴다", async () => {
  const router = renderAt("/models?sort=status&order=desc", { user: null });

  expect(
    await screen.findByRole("heading", { level: 1, name: "로그인" }),
  ).toBeDefined();
  expect(router.state.location.pathname).toBe("/login");
  expect(router.state.location.search).toEqual({
    redirect: "/models?sort=status&order=desc",
  });
});

test("로그인하면 원래 가려던 화면으로 돌아간다", async () => {
  const fetchMock = stubLoginResponse(200, TEST_USER);
  const router = renderAt("/login?redirect=%2Fmodels%3Fsort%3Dstatus", {
    user: null,
  });

  await fillAndSubmit("admin1@patron.dev", "secret");

  expect(
    await screen.findByRole("heading", { level: 1, name: "AI 모델 관리" }),
  ).toBeDefined();
  expect(router.state.location.pathname).toBe("/models");
  expect(router.state.location.search).toEqual({ sort: "status" });
  // 비밀번호는 요청 본문으로만 보낸다.
  const [request] = fetchMock.mock.calls[0];
  expect(await request.json()).toEqual({
    email: "admin1@patron.dev",
    password: "secret",
  });
});

test("돌아갈 주소가 없으면 고객 AI 사용 현황으로 간다", async () => {
  stubLoginResponse(200, TEST_USER);
  renderAt("/login", { user: null });

  await fillAndSubmit("admin1@patron.dev", "secret");

  expect(
    await screen.findByRole("heading", { level: 1, name: "고객 AI 사용 현황" }),
  ).toBeDefined();
});

test("서버가 거절하면 그 문구를 보여 주고 로그인 화면에 머무른다", async () => {
  stubLoginResponse(401, {
    code: "INVALID_CREDENTIALS",
    message: "이메일 또는 비밀번호가 올바르지 않습니다.",
  });
  const router = renderAt("/login", { user: null });

  await fillAndSubmit("admin1@patron.dev", "wrong");

  expect((await screen.findByRole("alert")).textContent).toBe(
    "이메일 또는 비밀번호가 올바르지 않습니다.",
  );
  expect(router.state.location.pathname).toBe("/login");
});

test("이미 로그인한 상태로 로그인 화면에 오면 기본 화면으로 보낸다", async () => {
  const router = renderAt("/login");

  await waitFor(() =>
    expect(router.state.location.pathname).toBe("/customer-usage"),
  );
});

test("세션이 만료되어 돌아온 경우에는 만료 안내를 보여 준다", async () => {
  renderAt("/login?reason=expired&redirect=%2Fmodels", { user: null });

  await screen.findByRole("heading", { level: 1, name: "로그인" });
  expect(screen.getByText("세션이 만료됐어요")).toBeDefined();
  expect(screen.getByText("다시 로그인해 주세요.")).toBeDefined();
});

test("처음 들어온 경우에는 만료 안내가 없다", async () => {
  renderAt("/login", { user: null });

  await screen.findByRole("heading", { level: 1, name: "로그인" });
  expect(screen.queryByText("세션이 만료됐어요")).toBeNull();
});

test("허용하지 않는 reason 값은 무시한다", async () => {
  const router = renderAt("/login?reason=hacked", { user: null });

  await screen.findByRole("heading", { level: 1, name: "로그인" });
  expect(router.state.location.search).toEqual({});
});
