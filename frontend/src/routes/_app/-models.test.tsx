// @vitest-environment jsdom
import { cleanup, fireEvent, screen, waitFor } from "@testing-library/react";
import { expect, test } from "vitest";
import { renderAt } from "../../test/renderAt";

type Router = ReturnType<typeof renderAt>;

/** 화면이 검증을 거쳐 실제로 쓰는 조회 조건 */
function appliedSearch(router: Router) {
  return router.state.matches.find((match) => match.routeId === "/_app/models")
    ?.search;
}

function sortStateOf(header: string) {
  return screen
    .getByRole("columnheader", { name: new RegExp(header) })
    .getAttribute("aria-sort");
}

test("주소의 정렬 조건을 표 머리글에 보여 준다", async () => {
  renderAt("/models?sort=status&order=desc");

  await screen.findByRole("table", { name: "등록된 AI 모델" });
  expect(sortStateOf("상태")).toBe("descending");
  expect(sortStateOf("표시 이름")).toBe("none");
});

test("머리글을 누르면 정렬 조건이 주소에 남는다", async () => {
  renderAt("/models");

  await screen.findByRole("table", { name: "등록된 AI 모델" });

  fireEvent.click(screen.getByRole("button", { name: /Model ID/ }));
  await waitFor(() => expect(sortStateOf("Model ID")).toBe("ascending"));

  fireEvent.click(screen.getByRole("button", { name: /Model ID/ }));
  await waitFor(() => expect(sortStateOf("Model ID")).toBe("descending"));
});

test("허용하지 않는 정렬 값은 무시한다", async () => {
  renderAt("/models?sort=password&order=sideways");

  await screen.findByRole("table", { name: "등록된 AI 모델" });
  for (const header of ["표시 이름", "Model ID", "상태"]) {
    expect(sortStateOf(header)).toBe("none");
  }
});

test("주소의 페이지 번호는 1 이상의 정수만 받는다", async () => {
  for (const [page, expected] of [
    ["2", 2],
    ["1", 1],
    ["0", undefined],
    ["-1", undefined],
    ["1.5", undefined],
    ["abc", undefined],
  ] as const) {
    const router = renderAt(`/models?page=${page}`);
    await screen.findByRole("table", { name: "등록된 AI 모델" });
    expect(appliedSearch(router)?.page).toBe(expected);
    cleanup();
  }
});

test("정렬을 바꾸면 1페이지로 돌아간다", async () => {
  const router = renderAt("/models?page=3");
  await screen.findByRole("table", { name: "등록된 AI 모델" });

  fireEvent.click(screen.getByRole("button", { name: /Model ID/ }));

  await waitFor(() =>
    expect(appliedSearch(router)).toEqual({ sort: "modelId", order: "asc" }),
  );
});

test("검색어를 바꾸면 1페이지로 돌아간다", async () => {
  const router = renderAt("/models?page=3");
  await screen.findByRole("table", { name: "등록된 AI 모델" });

  fireEvent.change(screen.getByRole("searchbox", { name: "모델 검색" }), {
    target: { value: "gpt" },
  });

  await waitFor(() => expect(appliedSearch(router)).toEqual({ q: "gpt" }));
});
