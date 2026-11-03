import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
  createMemoryHistory,
  createRouter,
  RouterProvider,
} from "@tanstack/react-router";
import { cleanup, render } from "@testing-library/react";
import { afterEach } from "vitest";
import {
  type CurrentUser,
  currentUserQueryOptions,
} from "../features/auth/api/auth";
import { routeTree } from "../routeTree.gen";

// 이 도구를 쓰는 테스트 파일에서는 테스트마다 화면을 지워, 앞 테스트의 화면이 섞이지 않게 한다.
afterEach(cleanup);

/** 로그인한 상태로 화면을 띄울 때 쓰는 관리자 */
export const TEST_USER: CurrentUser = {
  user_id: 1,
  user_code: "USR-001",
  name: "김관리",
  email: "admin1@patron.dev",
};

type RenderAtOptions = {
  /** 로그인 상태. null이면 로그인하지 않은 상태다. 기본은 TEST_USER로 로그인한 상태. */
  user?: CurrentUser | null;
};

/**
 * 실제 앱 라우트 전체를 주어진 주소에서 띄운다. 주소를 확인할 수 있게 라우터를 돌려준다.
 * 로그인 상태는 서버를 부르지 않고 쿼리 캐시에 미리 넣는다.
 */
export function renderAt(
  path: string,
  { user = TEST_USER }: RenderAtOptions = {},
) {
  // 테스트마다 캐시를 따로 두고, 실패 동작을 기다림 없이 확인하려고 재시도를 끈다.
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  queryClient.setQueryData(currentUserQueryOptions.queryKey, user);
  const router = createRouter({
    routeTree,
    history: createMemoryHistory({ initialEntries: [path] }),
    context: { queryClient },
  });
  render(
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
  return router;
}

type Match = ReturnType<typeof renderAt>["state"]["matches"][number];

/** 지금 띄운 그 화면의 매치. `.search`가 검증을 거쳐 화면이 실제로 쓰는 조회 조건이다. */
export function routeMatch<TRouteId extends Match["routeId"]>(
  router: ReturnType<typeof renderAt>,
  routeId: TRouteId,
) {
  return router.state.matches.find(
    (match): match is Extract<Match, { routeId: TRouteId }> =>
      match.routeId === routeId,
  );
}
