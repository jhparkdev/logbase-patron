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

/** 실제 앱 라우트 전체를 주어진 주소에서 띄운다. */
export function renderAt(path: string) {
  const router = createRouter({
    routeTree,
    history: createMemoryHistory({ initialEntries: [path] }),
  });
  render(<RouterProvider router={router} />);
}
