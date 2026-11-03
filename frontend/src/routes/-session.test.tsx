// @vitest-environment jsdom
import { fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import { currentUserQueryOptions } from "../features/auth/api/auth";
import { renderAt } from "../test/renderAt";

afterEach(() => vi.unstubAllGlobals());

/** 로그아웃 요청에 대한 서버 응답을 정해 둔다. 그 밖의 요청은 테스트가 실패하도록 거절한다. */
function stubLogoutResponse(status: number, body?: unknown) {
  const fetchMock = vi.fn(async (request: Request) => {
    const { pathname } = new URL(request.url);
    if (pathname === "/api/auth/logout" && request.method === "POST") {
      return body === undefined
        ? new Response(null, { status })
        : new Response(JSON.stringify(body), {
            status,
            headers: { "Content-Type": "application/json" },
          });
    }
    throw new Error(`예상하지 않은 요청: ${request.method} ${pathname}`);
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

test("화면 틀 헤더에 아이콘만 있는 로그아웃 버튼이 있고 이름으로 찾을 수 있다", async () => {
  renderAt("/models");

  const button = await screen.findByRole("button", { name: "로그아웃" });
  // 글자 없이 아이콘만 보이므로 화면 낭독기용 이름과 마우스 올림 설명을 둔다.
  expect(button.textContent).toBe("");
  expect(button.getAttribute("title")).toBe("로그아웃");
});

test("로그아웃하면 로그인 화면으로 가고 이전 사용자의 캐시를 비운다", async () => {
  stubLogoutResponse(204);
  const router = renderAt("/models");
  const queryClient = router.options.context.queryClient;

  fireEvent.click(await screen.findByRole("button", { name: "로그아웃" }));

  expect(
    await screen.findByRole("heading", { level: 1, name: "로그인" }),
  ).toBeDefined();
  // 로그아웃은 만료가 아니므로 만료 안내를 붙이지 않는다.
  expect(router.state.location.search).toEqual({});
  await waitFor(() =>
    expect(
      queryClient.getQueryData(currentUserQueryOptions.queryKey),
    ).toBeUndefined(),
  );
});

test("로그아웃이 실패하면 안내를 보여 주고 화면에 머무른다", async () => {
  stubLogoutResponse(500, { code: "INTERNAL_ERROR", message: "Traceback" });
  const router = renderAt("/models");

  fireEvent.click(await screen.findByRole("button", { name: "로그아웃" }));

  expect((await screen.findByRole("alert")).textContent).toBe(
    "로그아웃하지 못했어요. 다시 시도해 주세요.",
  );
  expect(router.state.location.pathname).toBe("/models");
});

test("세션이 끝난 것이 확인되면 로그인 화면으로 보내고 만료 안내와 돌아갈 주소를 붙인다", async () => {
  const router = renderAt("/models?sort=status");
  await screen.findByRole("heading", { level: 1, name: "AI 모델 관리" });

  // 서버가 /me에 401을 돌려줘 사용자 조회 결과가 null로 바뀐 상황
  router.options.context.queryClient.setQueryData(
    currentUserQueryOptions.queryKey,
    null,
  );

  await screen.findByRole("heading", { level: 1, name: "로그인" });
  expect(router.state.location.search).toEqual({
    redirect: "/models?sort=status",
    reason: "expired",
  });
  expect(screen.getByText("세션이 만료됐어요")).toBeDefined();
});
