// @vitest-environment jsdom
import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeAll, expect, test, vi } from "vitest";
import { MODEL_ROW } from "../../test/modelsApi";
import { renderAt } from "../../test/renderAt";
import {
  ACTIVE_MODEL,
  EXECUTION_PROVIDERS,
  RERUN_DRAFT,
  RUN_DETAIL,
  RUN_ID,
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
  vi.unstubAllGlobals();
});

const NEW_RUN = "01a1611f-3e80-73c5-a130-3efa5a1f7999";
const ASSET = "01a1611f-3e80-73c5-a130-3efa5a1f7700";
const JSON_HEADERS = { "Content-Type": "application/json" };
type Reply = { status: number; body: unknown };

/** P-04가 부르는 API 응답. 보낸 요청은 목록에 기록한다. 실제 OpenRouter는 부르지 않는다. */
function stub(overrides: Record<string, Reply> = {}) {
  const requests: { method: string; path: string; request: Request }[] = [];
  const routes = (method: string, path: string): Reply => {
    const key = `${method} ${path}`;
    if (overrides[key]) return overrides[key];
    if (key === "GET /api/models")
      return {
        status: 200,
        body: { items: [ACTIVE_MODEL], page: 1, page_size: 100, total: 1 },
      };
    if (path.endsWith("/execution-providers"))
      return { status: 200, body: EXECUTION_PROVIDERS };
    if (key === "GET /api/simulations/images/limits")
      return {
        status: 200,
        body: {
          max_count: 4,
          max_bytes: 5_242_880,
          mime_types: ["image/png"],
        },
      };
    if (key === "POST /api/simulations/images")
      return {
        status: 201,
        body: {
          asset_id: ASSET,
          mime_type: "image/png",
          file_size_bytes: 5,
          original_filename: "a.png",
        },
      };
    if (key === "POST /api/simulations")
      return { status: 202, body: { simulation_id: NEW_RUN } };
    if (path.endsWith("/rerun-draft"))
      return { status: 200, body: RERUN_DRAFT };
    if (path.endsWith("/cancel"))
      return {
        status: 200,
        body: { simulation_id: RUN_ID, status: "CANCELLED", results: [] },
      };
    return { status: 200, body: RUN_DETAIL };
  };
  vi.stubGlobal("fetch", async (request: Request) => {
    const { pathname } = new URL(request.url);
    requests.push({
      method: request.method,
      path: pathname,
      request: request.clone(),
    });
    const reply = routes(request.method, pathname);
    return new Response(JSON.stringify(reply.body), {
      status: reply.status,
      headers: JSON_HEADERS,
    });
  });
  const find = (method: string, path: string) =>
    requests.filter((item) => item.method === method && item.path === path);
  return { requests, find };
}

/** 모델 목록을 다 받아야 모델 검색 버튼이 켜진다. */
async function openPicker() {
  const button = await screen.findByRole("button", { name: "모델 검색" });
  await waitFor(() => expect(button.hasAttribute("disabled")).toBe(false));
  fireEvent.click(button);
}

async function chooseTwoProviders() {
  fireEvent.change(await screen.findByLabelText("Prompt"), {
    target: { value: "요약해 주세요." },
  });
  await openPicker();
  fireEvent.click(
    await screen.findByRole("checkbox", { name: "Mistral Nemo · DeepInfra" }),
  );
  fireEvent.click(
    screen.getByRole("checkbox", { name: "Mistral Nemo · DekaLLM" }),
  );
  fireEvent.click(screen.getByRole("button", { name: "선택 적용" }));
}

async function confirmRun() {
  const run = screen.getByRole("button", { name: "비교 실행" });
  await waitFor(() => expect(run.hasAttribute("disabled")).toBe(false));
  fireEvent.click(run);
  const dialog = await screen.findByRole("dialog", {
    name: "비교를 실행합니다",
  });
  fireEvent.click(within(dialog).getByRole("button", { name: "실행하기" }));
}

test("활성 모델만 요청해 서버 업체별로 보여 주고, 실행 전에는 비용 API를 부르지 않는다", async () => {
  const api = stub();
  renderAt("/simulator");
  await openPicker();
  expect(
    await screen.findByRole("checkbox", { name: "Mistral Nemo · DeepInfra" }),
  ).toBeDefined();
  expect(
    screen.getByRole("checkbox", { name: "Mistral Nemo · DekaLLM" }),
  ).toBeDefined();
  const list = api.find("GET", "/api/models")[0];
  expect(new URL(list.request.url).searchParams.get("status")).toBe("ACTIVE");
  expect(api.find("POST", "/api/simulations")).toEqual([]);
});

test("서버 업체를 받지 못한 모델은 고를 수 없게 안내하고 다른 모델은 고를 수 있다", async () => {
  stub({
    "GET /api/models": {
      status: 200,
      body: {
        items: [ACTIVE_MODEL, { ...MODEL_ROW, display_name: "GPT" }],
        page: 1,
        page_size: 100,
        total: 2,
      },
    },
    [`GET /api/models/${MODEL_ROW.model_id}/execution-providers`]: {
      status: 502,
      body: {
        code: "EXECUTION_PROVIDERS_UNAVAILABLE",
        message: "불러오지 못함",
      },
    },
  });
  renderAt("/simulator");
  await openPicker();
  expect(
    await screen.findByRole("checkbox", { name: "Mistral Nemo · DeepInfra" }),
  ).toBeDefined();
  expect(screen.getByText("서버 업체를 확인할 수 없습니다")).toBeDefined();
});

test("모델 목록 조회 실패와 다시 시도를 구분한다", async () => {
  stub({
    "GET /api/models": {
      status: 500,
      body: { code: "INTERNAL_ERROR", message: "내부" },
    },
  });
  renderAt("/simulator");
  expect(
    await screen.findByText("모델 목록을 불러오지 못했습니다"),
  ).toBeDefined();
  expect(screen.getByRole("button", { name: "다시 시도" })).toBeDefined();
});

test("확인 후 실행을 접수하고 주소에 실행 ID를 남겨 결과를 보여 준다", async () => {
  const api = stub();
  const router = renderAt("/simulator");
  await chooseTwoProviders();
  await confirmRun();
  await waitFor(() =>
    expect(router.state.location.search).toMatchObject({ run: NEW_RUN }),
  );
  const [post] = api.find("POST", "/api/simulations");
  expect(await post.request.json()).toEqual({
    test_type: "CUSTOM",
    prompt_text: "요약해 주세요.",
    input_text: null,
    json_schema: null,
    execution_config: {},
    models: [
      { model_id: 2, execution_provider: "DeepInfra", execution_config: {} },
      { model_id: 2, execution_provider: "DekaLLM", execution_config: {} },
    ],
    asset_ids: [],
  });
  expect(await screen.findByText("모델 응답 원문")).toBeDefined();
});

test("이미지를 먼저 올리고 받은 ID로 실행을 접수한다", async () => {
  const api = stub();
  renderAt("/simulator");
  await chooseTwoProviders();
  fireEvent.change(screen.getByLabelText(/이미지 \(선택사항\)/), {
    target: { files: [new File(["image"], "a.png", { type: "image/png" })] },
  });
  await confirmRun();
  await waitFor(() =>
    expect(api.find("POST", "/api/simulations")).toHaveLength(1),
  );
  const [upload] = api.find("POST", "/api/simulations/images");
  expect(upload.request.headers.get("content-type")).toContain(
    "multipart/form-data",
  );
  const [post] = api.find("POST", "/api/simulations");
  expect((await post.request.json()).asset_ids).toEqual([ASSET]);
});

test("이미지 업로드에 실패하면 실행을 접수하지 않고 서버 문구를 보여 준다", async () => {
  const api = stub({
    "POST /api/simulations/images": {
      status: 400,
      body: { code: "BAD_REQUEST", message: "이미지가 너무 큽니다." },
    },
  });
  renderAt("/simulator");
  await chooseTwoProviders();
  fireEvent.change(screen.getByLabelText(/이미지 \(선택사항\)/), {
    target: { files: [new File(["image"], "a.png", { type: "image/png" })] },
  });
  await confirmRun();
  expect(await screen.findByText("이미지가 너무 큽니다.")).toBeDefined();
  expect(api.find("POST", "/api/simulations")).toEqual([]);
});

test("서버가 실행을 거절하면 보여 주라고 준 문구를 표시한다", async () => {
  stub({
    "POST /api/simulations": {
      status: 400,
      body: { code: "BAD_REQUEST", message: "활성 모델만 실행할 수 있습니다." },
    },
  });
  renderAt("/simulator");
  await chooseTwoProviders();
  await confirmRun();
  expect(
    await screen.findByText("활성 모델만 실행할 수 있습니다."),
  ).toBeDefined();
});

test("주소의 실행 ID로 결과를 복원하고 진행 중이면 전체·모델별 취소를 보낸다", async () => {
  const running = {
    ...RUN_DETAIL,
    summary: { ...RUN_DETAIL.summary, status: "RUNNING", completed_at: null },
    results: [
      { ...RUN_DETAIL.results[0], status: "RUNNING" },
      { ...RUN_DETAIL.results[1], status: "RUNNING" },
    ],
  };
  const api = stub({
    [`GET /api/simulations/${RUN_ID}`]: { status: 200, body: running },
  });
  renderAt(`/simulator?run=${RUN_ID}`);
  const slotCancel = await screen.findByRole("button", {
    name: "Nova Micro · Amazon 실행 취소",
  });
  fireEvent.click(slotCancel);
  await waitFor(() =>
    expect(
      api.find("POST", `/api/simulations/${RUN_ID}/slots/2/cancel`),
    ).toHaveLength(1),
  );
  const cancelAll = await screen.findByRole("button", { name: "전체 취소" });
  await waitFor(() => expect(cancelAll.hasAttribute("disabled")).toBe(false));
  fireEvent.click(cancelAll);
  await waitFor(() =>
    expect(api.find("POST", `/api/simulations/${RUN_ID}/cancel`)).toHaveLength(
      1,
    ),
  );
});

test("결과 정렬은 주소에 남고 비용 미확인은 맨 뒤에 둔다", async () => {
  stub();
  renderAt(`/simulator?run=${RUN_ID}&sort=cost&direction=desc`);
  const table = await screen.findByRole("table", {
    name: /모델별 실행 상태/,
  });
  const rows = within(table).getAllByRole("row").slice(1);
  expect(rows[0].textContent).toContain("Mistral Nemo");
  expect(rows[1].textContent).toContain("미확인");
});

const CUSTOM_DRAFT = {
  ...RERUN_DRAFT,
  test_type: "CUSTOM",
  scenario_id: null,
  json_schema: null,
  models: [
    { ...RERUN_DRAFT.models[0], execution_provider: "DeepInfra" },
    {
      ...RERUN_DRAFT.models[0],
      execution_provider: "DekaLLM",
      execution_config: { temperature: 0.9 },
    },
  ],
};

test("재실행은 과거 입력을 복원하고 실행 전에는 호출하지 않으며 원본 ID를 함께 보낸다", async () => {
  const api = stub({
    [`GET /api/simulations/${RUN_ID}/rerun-draft`]: {
      status: 200,
      body: CUSTOM_DRAFT,
    },
  });
  const router = renderAt(`/simulator?sourceRun=${RUN_ID}`);
  const prompt = await screen.findByLabelText("Prompt");
  expect((prompt as HTMLTextAreaElement).value).toBe("과거 Prompt 원문");
  expect(api.find("POST", "/api/simulations")).toEqual([]);
  await confirmRun();
  await waitFor(() =>
    expect(router.state.location.search).toMatchObject({
      run: NEW_RUN,
      sourceRun: RUN_ID,
    }),
  );
  const [post] = api.find("POST", "/api/simulations");
  const body = await post.request.json();
  expect(body.rerun_of_simulation_id).toBe(RUN_ID);
  expect(body.prompt_text).toBe("과거 Prompt 원문");
  expect(body.models[1].execution_provider).toBe("DekaLLM");
});

test("지금 고를 수 없는 업체는 비우고 안내한다", async () => {
  stub({
    [`GET /api/simulations/${RUN_ID}/rerun-draft`]: {
      status: 200,
      body: {
        ...CUSTOM_DRAFT,
        models: [
          CUSTOM_DRAFT.models[0],
          { ...CUSTOM_DRAFT.models[0], execution_provider: "mock-provider" },
        ],
      },
    },
  });
  renderAt(`/simulator?sourceRun=${RUN_ID}`);
  expect(
    await screen.findByText(/현재 선택할 수 없는 모델의 비교 칸을 비웠습니다/),
  ).toBeDefined();
});

test("시나리오 실행은 직접 작성으로 바꾸지 않고 재실행을 막는다", async () => {
  stub();
  renderAt(`/simulator?sourceRun=${RUN_ID}`);
  expect(
    await screen.findByText("시나리오 실행의 재실행을 준비하고 있습니다"),
  ).toBeDefined();
  expect(screen.queryByLabelText("Prompt")).toBeNull();
});

test("없는 재실행 원본은 찾을 수 없다고 안내한다", async () => {
  stub({
    [`GET /api/simulations/${RUN_ID}/rerun-draft`]: {
      status: 404,
      body: { code: "NOT_FOUND", message: "없음" },
    },
  });
  renderAt(`/simulator?sourceRun=${RUN_ID}`);
  expect(
    await screen.findByText("재실행할 입력을 찾을 수 없습니다"),
  ).toBeDefined();
});
