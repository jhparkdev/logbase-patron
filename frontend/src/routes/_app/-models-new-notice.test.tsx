// @vitest-environment jsdom
import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeAll, expect, test, vi } from "vitest";
import {
  DISCOVERIES,
  NEW_MODELS,
  NO_NEW_MODELS,
  OPENROUTER,
  stubModelsApi,
} from "../../test/modelsApi";
import { renderAt } from "../../test/renderAt";

const TABLE = "등록된 AI 모델";
const NEW_PATH = "/api/models/openrouter/new";

beforeAll(() => {
  HTMLDialogElement.prototype.showModal = function () {
    this.open = true;
  };
});

afterEach(() => {
  vi.restoreAllMocks();
  localStorage.clear();
});

test("새 모델이 있으면 개수와 기간만 알리고 모델 이름은 보이지 않는다", async () => {
  stubModelsApi({ newModels: { status: 200, body: NEW_MODELS } });
  renderAt("/models");

  expect(await screen.findByText("새로운 모델이 나왔어요")).toBeTruthy();
  expect(
    screen.getByText("아직 등록하지 않은 모델 5개가 있어요."),
  ).toBeTruthy();
  expect(screen.queryByText(/Acme/)).toBeNull();
});

test("알림은 파랑이 아니라 노랑(경고) 색으로 보인다", async () => {
  stubModelsApi({ newModels: { status: 200, body: NEW_MODELS } });
  renderAt("/models");

  const title = await screen.findByText("새로운 모델이 나왔어요");

  const box = title.closest("div.rounded-2xl");
  expect(box?.classList.contains("bg-yellow-50")).toBe(true);
  expect(box?.classList.contains("bg-blue-50")).toBe(false);
});

test("최근 5일과 개수만 알면 되므로 모델은 1개만 서버에 요청한다", async () => {
  const { requests } = stubModelsApi({
    newModels: { status: 200, body: NEW_MODELS },
  });
  renderAt("/models");
  await screen.findByText("새로운 모델이 나왔어요");

  const request = requests.find(({ url }) => url.pathname === NEW_PATH);
  expect(Object.fromEntries(request?.url.searchParams ?? [])).toEqual({
    days: "5",
    limit: "1",
  });
});

test("등록하러 가기를 누르면 신규 모델 등록 패널이 열린다", async () => {
  stubModelsApi({ newModels: { status: 200, body: NEW_MODELS } });
  renderAt("/models");
  await screen.findByText("새로운 모델이 나왔어요");

  fireEvent.click(screen.getByRole("button", { name: "등록하러 가기" }));

  expect(
    await screen.findByRole("dialog", { name: "신규 모델 등록" }),
  ).toBeTruthy();
});

const OPENROUTER_PATH = "/api/models/openrouter";

const NEW_ONLY = {
  items: [
    {
      ...OPENROUTER.items[0],
      openrouter_model_id: "acme/fresh",
      name: "Acme: Fresh",
      created_at: "2026-11-02T13:29:14Z",
    },
  ],
  page: 1,
  page_size: 10,
  total: 1,
};

const openrouterRequests = (requests: { url: URL }[]) =>
  requests.filter(({ url }) => url.pathname === OPENROUTER_PATH);

test("알림의 등록하러 가기로 열면 최근 5일 새 모델만 보고 있다고 알리고 새 모델만 요청한다", async () => {
  const { requests } = stubModelsApi({
    newModels: { status: 200, body: NEW_MODELS },
    openrouter: { status: 200, body: NEW_ONLY },
  });
  renderAt("/models");
  await screen.findByText("새로운 모델이 나왔어요");

  fireEvent.click(screen.getByRole("button", { name: "등록하러 가기" }));

  const dialog = await screen.findByRole("dialog", { name: "신규 모델 등록" });
  expect(
    await within(dialog).findByText(
      "최근 5일 안에 올라온 새 모델만 보고 있어요.",
    ),
  ).toBeTruthy();
  expect(await within(dialog).findByText("Acme: Fresh")).toBeTruthy();
  expect(within(dialog).getByText("2026-11-02 출시")).toBeTruthy();
  const [request] = openrouterRequests(requests);
  expect(request.url.searchParams.get("new_days")).toBe("5");
});

test("전체 모델 보기를 누르면 새 모델 조건을 빼고 전체를 다시 요청한다", async () => {
  const { requests } = stubModelsApi({
    newModels: { status: 200, body: NEW_MODELS },
    openrouter: { status: 200, body: NEW_ONLY },
  });
  renderAt("/models");
  await screen.findByText("새로운 모델이 나왔어요");
  fireEvent.click(screen.getByRole("button", { name: "등록하러 가기" }));
  const dialog = await screen.findByRole("dialog", { name: "신규 모델 등록" });
  await within(dialog).findByText("Acme: Fresh");

  fireEvent.click(
    within(dialog).getByRole("button", { name: "전체 모델 보기" }),
  );

  await waitFor(() => {
    const last = openrouterRequests(requests).at(-1);
    expect(last?.url.searchParams.has("new_days")).toBe(false);
  });
  expect(
    within(dialog).queryByText("최근 5일 안에 올라온 새 모델만 보고 있어요."),
  ).toBeNull();
});

test("신규 모델 등록 버튼으로 열면 새 모델 조건 없이 전체를 보여 준다", async () => {
  const { requests } = stubModelsApi({
    newModels: { status: 200, body: NEW_MODELS },
  });
  renderAt("/models");
  await screen.findByText("새로운 모델이 나왔어요");

  fireEvent.click(screen.getByRole("button", { name: "신규 모델 등록" }));

  const dialog = await screen.findByRole("dialog", { name: "신규 모델 등록" });
  await within(dialog).findByText("openai/gpt-4o");
  expect(
    openrouterRequests(requests).every(
      ({ url }) => !url.searchParams.has("new_days"),
    ),
  ).toBe(true);
  expect(within(dialog).queryByText(/새 모델만 보고 있어요/)).toBeNull();
});

test("새 모델이 없으면 알림을 보이지 않는다", async () => {
  const { requests } = stubModelsApi({
    newModels: { status: 200, body: NO_NEW_MODELS },
  });
  renderAt("/models");
  await screen.findByRole("table", { name: TABLE });

  await waitFor(() =>
    expect(requests.some(({ url }) => url.pathname === NEW_PATH)).toBe(true),
  );
  expect(screen.queryByText(/새 모델 .*개가 올라왔어요/)).toBeNull();
  expect(screen.queryByRole("button", { name: "등록하러 가기" })).toBeNull();
});

test("알림을 불러오지 못해도 알리지 않고 모델 표는 그대로 보인다", async () => {
  const { requests } = stubModelsApi({
    newModels: {
      status: 502,
      body: { code: "OPENROUTER_UNAVAILABLE", message: "불러오지 못했어요" },
    },
  });
  renderAt("/models");

  expect(await screen.findByRole("table", { name: TABLE })).toBeTruthy();
  await waitFor(() =>
    expect(requests.some(({ url }) => url.pathname === NEW_PATH)).toBe(true),
  );
  expect(screen.queryByText(/새 모델 .*개가 올라왔어요/)).toBeNull();
  expect(screen.queryByText("불러오지 못했어요")).toBeNull();
});

test("비교한 새 모델이 있으면 결과와 넘어간 이유를 보여 준다", async () => {
  stubModelsApi({ discoveries: { status: 200, body: DISCOVERIES } });
  renderAt("/models");

  const section = await screen.findByRole("region", {
    name: "새 모델 비교 결과",
  });

  expect(within(section).getByText("Acme: New")).toBeTruthy();
  expect(within(section).getByText("확인해 볼 만해요")).toBeTruthy();
  expect(
    within(section).getByText("기본 모델 대비 비용 50.0% 저렴해요"),
  ).toBeTruthy();
  expect(
    within(section).getByText(
      "단가가 기본 모델보다 많이 비싸거나 알 수 없어 비교하지 않았어요",
    ),
  ).toBeTruthy();
});

test("비교한 새 모델이 없으면 비교 결과 구역을 그리지 않는다", async () => {
  stubModelsApi();
  renderAt("/models");
  await screen.findByRole("table", { name: TABLE });

  expect(
    screen.queryByRole("region", { name: "새 모델 비교 결과" }),
  ).toBeNull();
});

test("비교 결과를 불러오지 못해도 모델 목록은 그대로 보인다", async () => {
  stubModelsApi({ discoveries: { status: 500, body: {} } });
  renderAt("/models");

  expect(await screen.findByRole("table", { name: TABLE })).toBeTruthy();
  expect(
    screen.queryByRole("region", { name: "새 모델 비교 결과" }),
  ).toBeNull();
});

const SEEN_KEY = "patron.newModelsSeenAt";
const LATEST = NEW_MODELS.items[0].created_at;

function modelsMenu() {
  return screen
    .getByRole("navigation", { name: "주 메뉴" })
    .querySelector('a[href="/models"]') as HTMLElement;
}

test("확인하지 않은 새 모델이 있으면 다른 화면에서도 모델 관리 메뉴에 표시한다", async () => {
  stubModelsApi({ newModels: { status: 200, body: NEW_MODELS } });
  renderAt("/internal-budget");

  await waitFor(() =>
    expect(
      within(modelsMenu()).getByRole("img", { name: "새로운 모델이 나왔어요" }),
    ).toBeTruthy(),
  );
});

test("가장 새 모델까지 확인했으면 메뉴에 표시하지 않는다", async () => {
  localStorage.setItem(SEEN_KEY, LATEST ?? "");
  const { requests } = stubModelsApi({
    newModels: { status: 200, body: NEW_MODELS },
  });
  renderAt("/internal-budget");

  await waitFor(() =>
    expect(requests.some(({ url }) => url.pathname === NEW_PATH)).toBe(true),
  );
  expect(within(modelsMenu()).queryByRole("img")).toBeNull();
});

test("모델 관리 화면을 열면 지금 새 모델까지 확인한 것으로 남기고 표시를 지운다", async () => {
  stubModelsApi({ newModels: { status: 200, body: NEW_MODELS } });
  renderAt("/models");

  await screen.findByText("새로운 모델이 나왔어요");
  await waitFor(() => expect(localStorage.getItem(SEEN_KEY)).toBe(LATEST));
  expect(within(modelsMenu()).queryByRole("img")).toBeNull();
});
