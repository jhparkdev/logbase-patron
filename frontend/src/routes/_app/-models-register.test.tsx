// @vitest-environment jsdom
import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeAll, expect, test, vi } from "vitest";
import { OPENROUTER, stubModelsApi } from "../../test/modelsApi";
import { renderAt } from "../../test/renderAt";

const TABLE = "등록된 AI 모델";
const PANEL = "신규 모델 등록";

beforeAll(() => {
  HTMLDialogElement.prototype.showModal = function () {
    this.open = true;
  };
});

afterEach(() => vi.restoreAllMocks());

type Panel = ReturnType<typeof within>;

async function openPanel(): Promise<Panel> {
  renderAt("/models");
  await screen.findByRole("table", { name: TABLE });
  fireEvent.click(screen.getByRole("button", { name: PANEL }));
  const panel = within(screen.getByRole("dialog", { name: PANEL }));
  await panel.findByText("openai/gpt-4o");
  return panel;
}

/** 목록에서 그 Model ID 항목의 라디오. 고른 뒤에는 등록 정보에도 같은 ID가 있어 목록 항목(label) 쪽을 찾음 */
const radioOf = (panel: Panel, id: string) => {
  const item = panel
    .getAllByText(id)
    .map((element: HTMLElement) => element.closest("label"))
    .find((label: HTMLElement | null) => label !== null);
  if (!item) throw new Error(`${id} 항목을 찾지 못했다`);
  return within(item).getByRole("radio") as HTMLInputElement;
};

const select = (panel: Panel, id: string) =>
  fireEvent.click(radioOf(panel, id));

const posts = (requests: { url: URL; method: string; body: unknown }[]) =>
  requests.filter(({ method }) => method === "POST");

test("신규 모델 등록 버튼을 누르면 패널이 열리고 OpenRouter 모델 목록을 요청한다", async () => {
  const { requests } = stubModelsApi();
  await openPanel();

  const request = requests.find(
    ({ url }) => url.pathname === "/api/models/openrouter",
  );
  expect(Object.fromEntries(request?.url.searchParams ?? [])).toEqual({
    page: "1",
    page_size: "10",
  });
});

test("모델마다 이름, ID, 제공사, 입출력 형식, 지원 기능, Context, 단가를 보여 준다", async () => {
  stubModelsApi();
  const panel = await openPanel();

  expect(panel.getByText("GPT-4o")).toBeTruthy();
  expect(panel.getAllByText("openai").length).toBeGreaterThan(0);
  expect(panel.getAllByText("텍스트·이미지 → 텍스트").length).toBe(2);
  expect(panel.getAllByText("JSON").length).toBe(2);
  expect(panel.getAllByText("함수 호출").length).toBe(2);
  expect(
    panel.getAllByText(
      /Context 128,000 토큰 · 입력 2\.50 · 출력 10\.00 USD\/1M/,
    ).length,
  ).toBeGreaterThan(0);
});

test("이미 등록된 모델은 배지를 붙이고 고를 수 없다", async () => {
  stubModelsApi();
  const panel = await openPanel();

  expect(panel.getByText("이미 등록됨")).toBeTruthy();
  expect(radioOf(panel, "openai/gpt-4o-mini").disabled).toBe(true);
  expect(radioOf(panel, "openai/gpt-4o").disabled).toBe(false);
});

test("단가를 모르는 모델은 0이 아니라 가격 미확인 배지다", async () => {
  stubModelsApi();
  const panel = await openPanel();

  expect(panel.getByText("가격 미확인")).toBeTruthy();
  expect(panel.queryByText(/입력 0\.00/)).toBeNull();
});

test("모델을 고르기 전에는 등록 정보 입력 칸이 없다", async () => {
  stubModelsApi();
  const panel = await openPanel();

  expect(panel.queryByRole("textbox", { name: "표시 이름" })).toBeNull();
  expect(panel.queryByRole("button", { name: "등록" })).toBeNull();
});

test("모델을 고르면 Model ID와 OpenRouter 이름이 채워진 등록 정보가 나온다", async () => {
  stubModelsApi();
  const panel = await openPanel();

  select(panel, "openai/gpt-4o");

  expect(panel.getByText("Model ID").nextSibling?.textContent).toBe(
    "openai/gpt-4o",
  );
  expect(
    (panel.getByRole("textbox", { name: "표시 이름" }) as HTMLInputElement)
      .value,
  ).toBe("GPT-4o");
  expect(
    (panel.getByRole("textbox", { name: "용도 (선택)" }) as HTMLInputElement)
      .value,
  ).toBe("");
  expect(panel.getByText(/검증 중/)).toBeTruthy();
});

test("검색어를 입력하면 그 검색어로 1페이지를 다시 요청한다", async () => {
  const { requests } = stubModelsApi();
  const panel = await openPanel();

  fireEvent.change(
    panel.getByRole("searchbox", { name: "OpenRouter 모델 검색" }),
    {
      target: { value: "gpt" },
    },
  );

  await waitFor(() => {
    const last = requests
      .filter(({ url }) => url.pathname === "/api/models/openrouter")
      .at(-1);
    expect(last?.url.searchParams.get("q")).toBe("gpt");
    expect(last?.url.searchParams.get("page")).toBe("1");
  });
});

test("페이지를 옮기면 그 페이지를 요청한다", async () => {
  const { requests } = stubModelsApi({
    openrouter: { status: 200, body: { ...OPENROUTER, total: 25 } },
  });
  const panel = await openPanel();

  fireEvent.click(panel.getByRole("button", { name: "2" }));

  await waitFor(() => {
    const last = requests
      .filter(({ url }) => url.pathname === "/api/models/openrouter")
      .at(-1);
    expect(last?.url.searchParams.get("page")).toBe("2");
  });
});

test("등록하면 입력한 값을 보내고, 패널을 닫으며, 목록과 제공사를 다시 불러온다", async () => {
  const { requests } = stubModelsApi();
  const panel = await openPanel();
  const count = (path: string) =>
    requests.filter(({ url }) => url.pathname === path).length;
  const listBefore = count("/api/models") - posts(requests).length;
  const providersBefore = count("/api/models/providers");
  select(panel, "openai/gpt-4o");

  fireEvent.change(panel.getByRole("textbox", { name: "표시 이름" }), {
    target: { value: "  우리 GPT  " },
  });
  fireEvent.change(panel.getByRole("textbox", { name: "용도 (선택)" }), {
    target: { value: "요약 비교용" },
  });
  fireEvent.click(panel.getByRole("button", { name: "등록" }));

  await waitFor(() =>
    expect(screen.queryByRole("dialog", { name: PANEL })).toBeNull(),
  );
  expect(posts(requests)).toHaveLength(1);
  expect(posts(requests)[0].body).toEqual({
    openrouter_model_id: "openai/gpt-4o",
    display_name: "우리 GPT",
    purpose: "요약 비교용",
  });
  await waitFor(() =>
    expect(count("/api/models") - posts(requests).length).toBe(listBefore + 1),
  );
  await waitFor(() =>
    expect(count("/api/models/providers")).toBe(providersBefore + 1),
  );
});

test("표시 이름이 비어 있으면 요청 없이 이유를 알린다", async () => {
  const { requests } = stubModelsApi();
  const panel = await openPanel();
  select(panel, "openai/gpt-4o");

  fireEvent.change(panel.getByRole("textbox", { name: "표시 이름" }), {
    target: { value: "   " },
  });
  fireEvent.click(panel.getByRole("button", { name: "등록" }));

  expect(await panel.findByText("표시 이름을 입력해 주세요.")).toBeTruthy();
  expect(posts(requests)).toHaveLength(0);
});

test("서버가 등록을 거절하면 서버 문구를 보여 주고 패널과 선택을 유지한다", async () => {
  stubModelsApi({
    register: {
      status: 409,
      body: {
        code: "MODEL_ALREADY_REGISTERED",
        message: "이미 등록된 모델입니다.",
      },
    },
  });
  const panel = await openPanel();
  select(panel, "openai/gpt-4o");

  fireEvent.click(panel.getByRole("button", { name: "등록" }));

  expect((await panel.findByRole("alert")).textContent).toBe(
    "이미 등록된 모델입니다.",
  );
  expect(radioOf(panel, "openai/gpt-4o").checked).toBe(true);
});

test("OpenRouter 목록을 불러오지 못하면 알리고 다시 시도하면 불러온다", async () => {
  const { replies } = stubModelsApi({
    openrouter: {
      status: 502,
      body: {
        code: "OPENROUTER_UNAVAILABLE",
        message: "OpenRouter 모델 목록을 불러오지 못했습니다.",
      },
    },
  });
  renderAt("/models");
  await screen.findByRole("table", { name: TABLE });
  fireEvent.click(screen.getByRole("button", { name: PANEL }));
  const panel = within(screen.getByRole("dialog", { name: PANEL }));
  expect(
    await panel.findByText("OpenRouter 모델 목록을 불러오지 못했어요"),
  ).toBeTruthy();

  replies.openrouter = { status: 200, body: OPENROUTER };
  fireEvent.click(panel.getByRole("button", { name: "다시 시도" }));

  expect(await panel.findByText("openai/gpt-4o")).toBeTruthy();
});

test("결과가 없으면 조건에 맞는 모델이 없다고 알린다", async () => {
  stubModelsApi({
    openrouter: {
      status: 200,
      body: { items: [], page: 1, page_size: 10, total: 0 },
    },
  });
  renderAt("/models");
  await screen.findByRole("table", { name: TABLE });
  fireEvent.click(screen.getByRole("button", { name: PANEL }));
  const panel = within(screen.getByRole("dialog", { name: PANEL }));

  expect(await panel.findByText("조건에 맞는 모델이 없어요")).toBeTruthy();
});

test("닫기를 누르면 패널이 닫힌다", async () => {
  stubModelsApi();
  const panel = await openPanel();

  fireEvent.click(panel.getByRole("button", { name: "닫기" }));

  await waitFor(() =>
    expect(screen.queryByRole("dialog", { name: PANEL })).toBeNull(),
  );
});
