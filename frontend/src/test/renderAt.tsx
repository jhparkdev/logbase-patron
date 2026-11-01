import {
  createMemoryHistory,
  createRouter,
  RouterProvider,
} from "@tanstack/react-router";
import { cleanup, render } from "@testing-library/react";
import { afterEach } from "vitest";
import { routeTree } from "../routeTree.gen";

// 이 도구를 쓰는 테스트 파일에서는 테스트마다 화면을 지워, 앞 테스트의 화면이 섞이지 않게 한다.
afterEach(cleanup);

/** 실제 앱 라우트 전체를 주어진 주소에서 띄운다. 주소를 확인할 수 있게 라우터를 돌려준다. */
export function renderAt(path: string) {
  const router = createRouter({
    routeTree,
    history: createMemoryHistory({ initialEntries: [path] }),
  });
  render(<RouterProvider router={router} />);
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
