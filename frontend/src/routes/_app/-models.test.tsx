// @vitest-environment jsdom
import { cleanup, fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeAll, expect, test } from "vitest";
import { renderAt, routeMatch } from "../../test/renderAt";

// jsdom에는 모달 dialog 열기가 없어서, 브라우저처럼 open 속성만 켠다.
beforeAll(() => {
  HTMLDialogElement.prototype.showModal = function () {
    this.open = true;
  };
});

const ROUTE_ID = "/_app/models";

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
    expect(routeMatch(router, ROUTE_ID)?.search?.page).toBe(expected);
    cleanup();
  }
});

test("정렬을 바꾸면 1페이지로 돌아간다", async () => {
  const router = renderAt("/models?page=3");
  await screen.findByRole("table", { name: "등록된 AI 모델" });

  fireEvent.click(screen.getByRole("button", { name: /Model ID/ }));

  await waitFor(() =>
    expect(routeMatch(router, ROUTE_ID)?.search).toEqual({
      sort: "modelId",
      order: "asc",
    }),
  );
});

test("검색어를 바꾸면 1페이지로 돌아간다", async () => {
  const router = renderAt("/models?page=3");
  await screen.findByRole("table", { name: "등록된 AI 모델" });

  fireEvent.change(screen.getByRole("searchbox", { name: "모델 검색" }), {
    target: { value: "gpt" },
  });

  await waitFor(() =>
    expect(routeMatch(router, ROUTE_ID)?.search).toEqual({ q: "gpt" }),
  );
});

test("주소에 모델 번호가 있으면 상세 패널을 연다", async () => {
  renderAt("/models?model=3");

  expect(await screen.findByRole("dialog", { name: "모델 상세" })).toBeTruthy();
});

test("모델 번호가 1 이상의 정수가 아니면 상세 패널을 열지 않는다", async () => {
  for (const model of ["0", "-1", "1.5", "abc"]) {
    renderAt(`/models?model=${model}`);
    await screen.findByRole("table", { name: "등록된 AI 모델" });
    expect(screen.queryByRole("dialog")).toBeNull();
    cleanup();
  }
});

test("닫기를 누르면 패널이 닫히고 다른 조회 조건은 남는다", async () => {
  const router = renderAt("/models?q=gpt&model=3");
  await screen.findByRole("dialog", { name: "모델 상세" });

  fireEvent.click(screen.getByRole("button", { name: "닫기" }));

  await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
  expect(routeMatch(router, ROUTE_ID)?.search).toEqual({ q: "gpt" });
});

test("Esc를 누르면 패널이 닫힌다", async () => {
  renderAt("/models?model=3");
  const panel = await screen.findByRole("dialog", { name: "모델 상세" });

  fireEvent(panel, new Event("cancel", { cancelable: true }));

  await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
});
