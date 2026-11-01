// @vitest-environment jsdom
import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeAll, expect, test, vi } from "vitest";
import { renderAt } from "../../test/renderAt";
import { RUN_ID, stubHistoryApi } from "../../test/simulationHistoryApi";

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
  vi.unstubAllGlobals();
});
const show = renderAt;
const listRequests = (requests: URL[]) =>
  requests.filter((url) => url.pathname === "/api/simulations");

test("URL 조건으로 이력을 조회해 서버가 준 행을 표시한다", async () => {
  const { requests } = stubHistoryApi();
  show(
    "/simulation-history?from=2026-10-01&to=2026-10-30&status=FAILED&model=%222%22&page=2&sort=status&direction=asc",
  );
  expect(await screen.findByRole("button", { name: RUN_ID })).toBeDefined();
  expect(screen.getByText("PRODUCT_DESCRIPTION")).toBeDefined();
  expect(
    within(screen.getAllByRole("row")[1]).getByText("부분 성공"),
  ).toBeDefined();
  expect(screen.getByText("미확인 1건 미반영")).toBeDefined();
  const query = listRequests(requests)[0].searchParams;
  expect(Object.fromEntries(query)).toEqual({
    start_date: "2026-10-01",
    end_date: "2026-10-30",
    status: "FAILED",
    model_id: "2",
    page: "2",
    page_size: "10",
    sort: "status",
    direction: "asc",
  });
});

test("조회 결과 없음과 조회 실패를 구분하고 실패하면 다시 시도한다", async () => {
  const { replies } = stubHistoryApi({
    list: { status: 500, body: { code: "INTERNAL", message: "내부 오류" } },
  });
  show("/simulation-history");
  expect(
    await screen.findByText("실행 이력을 불러오지 못했어요"),
  ).toBeDefined();
  expect(screen.queryByText("내부 오류")).toBeNull();
  replies.list = { status: 200, body: { items: [], total: 0 } };
  fireEvent.click(screen.getByRole("button", { name: "다시 시도" }));
  expect(
    await screen.findByText("조건에 맞는 실행 이력이 없어요"),
  ).toBeDefined();
});

test("모델 필터 선택지를 등록된 모델로 채우고 시나리오 필터는 숨긴다", async () => {
  stubHistoryApi();
  show("/simulation-history");
  const model = await screen.findByRole("combobox", { name: "모델" });
  expect(
    await within(model).findByRole("option", { name: "Mistral Nemo" }),
  ).toBeDefined();
  expect(screen.queryByRole("combobox", { name: "시나리오" })).toBeNull();
});

test("실제 이력 화면의 조회 조건을 바꿔도 스크롤을 초기화하지 않는다", async () => {
  stubHistoryApi();
  const router = show("/simulation-history?page=2");
  const filter = await screen.findByLabelText("Simulation ID");
  await waitFor(() => expect(router.state.status).toBe("idle"));
  fireEvent.change(filter, { target: { value: RUN_ID } });
  const button = screen.getByRole("button", { name: "조회" });
  vi.mocked(window.scrollTo).mockClear();
  fireEvent.click(button);
  await waitFor(() =>
    expect(router.state.location.search).toMatchObject({
      simulationId: RUN_ID,
      page: 1,
    }),
  );
  expect(window.scrollTo).not.toHaveBeenCalled();
});

test("상세를 열면 당시 입력과 모델별 결과를 조회해 표시한다", async () => {
  const { requests } = stubHistoryApi();
  show("/simulation-history");
  fireEvent.click(await screen.findByRole("button", { name: RUN_ID }));
  const dialog = within(
    await screen.findByRole("dialog", { name: "시뮬레이션 실행 상세" }),
  );
  expect(await dialog.findByText("과거 Prompt 원문")).toBeDefined();
  expect(dialog.getByText("Nova Micro · Amazon")).toBeDefined();
  expect(
    dialog.getByRole("heading", { name: "시뮬레이션 결과 요약" }),
  ).toBeDefined();
  expect(dialog.getByText("모델 응답 원문")).toBeDefined();
  // 공통 값(0.3)과 다른 모델별 값을 구분해 보여 준다
  expect(dialog.getByText("공통 Temperature").nextSibling?.textContent).toBe(
    "0.3",
  );
  const [first, second] = dialog.getAllByRole("article");
  expect(within(first).getByText("0.9")).toBeDefined();
  expect(within(second).getByText("모델 기본값")).toBeDefined();
  // 지금은 비활성인 모델도 실행 당시 상태를 따로 보여 준다
  expect(within(second).getByText("실행 당시 모델 상태: 활성")).toBeDefined();
  expect(dialog.getByText("비활성")).toBeDefined();
  expect(
    requests.some((url) => url.pathname === `/api/simulations/${RUN_ID}`),
  ).toBe(true);
  expect(
    requests.some(
      (url) => url.pathname === `/api/simulations/${RUN_ID}/rerun-draft`,
    ),
  ).toBe(true);
});

test("상세를 열기 전에는 상세 API를 부르지 않는다", async () => {
  const { requests } = stubHistoryApi();
  show(`/simulation-history?selected=${RUN_ID}&detail=false`);
  await screen.findByRole("button", { name: RUN_ID });
  expect(
    requests.filter((url) => url.pathname.startsWith(`/api/simulations/`)),
  ).toEqual([]);
});

test("없는 실행은 조회 실패와 다른 문구로 안내한다", async () => {
  stubHistoryApi({
    detail: {
      status: 404,
      body: { code: "NOT_FOUND", message: "없음" },
    },
  });
  show(`/simulation-history?selected=${RUN_ID}&detail=true`);
  expect(await screen.findByText("실행 기록을 찾을 수 없어요")).toBeDefined();
  expect(screen.queryByText("실행 상세를 불러오지 못했어요")).toBeNull();
});

test("상세 조회 실패는 다시 시도할 수 있다", async () => {
  const { replies } = stubHistoryApi({
    detail: { status: 500, body: { code: "INTERNAL", message: "오류" } },
  });
  show(`/simulation-history?selected=${RUN_ID}&detail=true`);
  expect(
    await screen.findByText("실행 상세를 불러오지 못했어요"),
  ).toBeDefined();
  replies.detail = undefined;
  fireEvent.click(
    within(screen.getByRole("dialog")).getByRole("button", {
      name: "다시 시도",
    }),
  );
  expect(await screen.findByText("과거 Prompt 원문")).toBeDefined();
});

test("주소로 복원한 상세를 닫아도 조회 기간·필터·정렬·선택 ID를 유지한다", async () => {
  stubHistoryApi();
  const router = show(
    `/simulation-history?from=2026-10-01&to=2026-10-29&status=FAILED&sort=costStatus&direction=asc&page=2&selected=${RUN_ID}&detail=true`,
  );
  await screen.findByRole("dialog", { name: "시뮬레이션 실행 상세" });
  fireEvent.click(screen.getByRole("button", { name: "닫기" }));
  await waitFor(() =>
    expect(router.state.location.search).toMatchObject({
      from: "2026-10-01",
      to: "2026-10-29",
      status: "FAILED",
      sort: "costStatus",
      direction: "asc",
      page: 2,
      selected: RUN_ID,
      detail: false,
    }),
  );
  expect((screen.getByLabelText("조회 시작일") as HTMLInputElement).value).toBe(
    "2026-10-01",
  );
});

test("다시 준비하면 원본 ID만 전달하고 P-04 복원이 연결되기 전에는 완료로 표시하지 않는다", async () => {
  stubHistoryApi();
  const router = show(`/simulation-history?selected=${RUN_ID}&detail=true`);
  fireEvent.click(
    await screen.findByRole("button", { name: "이 조건으로 다시 준비" }),
  );
  await waitFor(() =>
    expect(router.state.location.search).toMatchObject({ sourceRun: RUN_ID }),
  );
  expect(
    await screen.findByText("재실행 조건 불러오기를 준비하고 있습니다"),
  ).toBeDefined();
  expect(router.state.location.href).not.toContain("Prompt");
});

test("서비스의 재실행 주소에는 원본 ID만 전달하고 API가 없으면 복원 완료로 표시하지 않는다", async () => {
  const router = show("/simulator?sourceRun=run-1");
  expect(
    await screen.findByText("재실행 조건 불러오기를 준비하고 있습니다"),
  ).toBeDefined();
  expect(screen.queryByLabelText("Prompt")).toBeNull();
  fireEvent.click(screen.getByRole("link", { name: "새 조건으로 준비하기" }));
  await waitFor(() =>
    expect(router.state.location.search.sourceRun).toBeUndefined(),
  );
  expect(await screen.findByLabelText("Prompt")).toBeDefined();
});
