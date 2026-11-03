// @vitest-environment jsdom
import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeAll, expect, test, vi } from "vitest";
import { stubModelsApi } from "../../test/modelsApi";
import { renderAt, routeMatch } from "../../test/renderAt";

const ROUTE_ID = "/_app/models";
const TABLE = "등록된 AI 모델";
const EMPTY_PAGE = { items: [], total: 0, page: 1, page_size: 10 };

beforeAll(() => {
  HTMLDialogElement.prototype.showModal = function () {
    this.open = true;
  };
});

afterEach(() => vi.restoreAllMocks());

const providerSelect = () => screen.getByRole("combobox", { name: "Provider" });
const statusSelect = () => screen.getByRole("combobox", { name: "상태" });

/** 제공사 선택지가 서버 응답으로 채워질 때까지 기다림 */
async function waitForProviders() {
  const select = await screen.findByRole("combobox", { name: "Provider" });
  await within(select).findByRole("option", { name: "openai (3)" });
}

function optionLabels(select: HTMLElement) {
  return within(select)
    .getAllByRole("option")
    .map((option) => option.textContent);
}

function lastParams(requests: { url: URL }[]) {
  return requests[requests.length - 1].url.searchParams;
}

test("제공사 선택지는 서버가 준 제공사다", async () => {
  stubModelsApi();
  renderAt("/models");

  await waitForProviders();

  expect(optionLabels(providerSelect())).toEqual([
    "Provider 전체",
    "openai (3)",
    "mistralai (1)",
  ]);
});

test("상태 선택지는 전체와 세 상태를 한국어로 보여 준다", async () => {
  stubModelsApi();
  renderAt("/models");

  await screen.findByRole("table", { name: TABLE });

  expect(optionLabels(statusSelect())).toEqual([
    "상태 전체",
    "검증 중",
    "사용 중",
    "사용 중단",
  ]);
});

test("주소의 제공사와 상태를 선택 상자에 보여 준다", async () => {
  stubModelsApi();
  renderAt("/models?provider=openai&status=INACTIVE");

  await waitForProviders();

  expect((providerSelect() as HTMLSelectElement).value).toBe("openai");
  expect((statusSelect() as HTMLSelectElement).value).toBe("INACTIVE");
});

test("제공사를 고르면 주소에 남고 1페이지로 돌아가 그 조건으로 요청한다", async () => {
  const { requests } = stubModelsApi();
  const router = renderAt("/models?page=3");
  await waitForProviders();

  fireEvent.change(providerSelect(), { target: { value: "openai" } });

  await waitFor(() =>
    expect(routeMatch(router, ROUTE_ID)?.search).toEqual({
      provider: "openai",
    }),
  );
  await waitFor(() => {
    expect(lastParams(requests).get("provider")).toBe("openai");
    expect(lastParams(requests).get("page")).toBe("1");
  });
});

test("상태를 고르면 주소에 남고 그 상태로 요청한다", async () => {
  const { requests } = stubModelsApi();
  const router = renderAt("/models?page=2");
  await screen.findByRole("table", { name: TABLE });

  fireEvent.change(statusSelect(), { target: { value: "ACTIVE" } });

  await waitFor(() =>
    expect(routeMatch(router, ROUTE_ID)?.search).toEqual({ status: "ACTIVE" }),
  );
  await waitFor(() => {
    expect(lastParams(requests).getAll("status")).toEqual(["ACTIVE"]);
    expect(lastParams(requests).get("page")).toBe("1");
  });
});

test("전체를 고르면 그 조건만 지우고 나머지는 남긴다", async () => {
  const router = renderAt("/models?provider=openai&status=ACTIVE&q=gpt");
  stubModelsApi();
  await waitForProviders();

  fireEvent.change(providerSelect(), { target: { value: "" } });

  await waitFor(() =>
    expect(routeMatch(router, ROUTE_ID)?.search).toEqual({
      status: "ACTIVE",
      q: "gpt",
    }),
  );
});

test("검색어 없이 선택 조건만 걸려도 조건에 맞는 모델이 없다고 알린다", async () => {
  stubModelsApi({ list: { status: 200, body: EMPTY_PAGE } });
  renderAt("/models?status=ACTIVE");

  expect(await screen.findByText("조건에 맞는 모델이 없어요")).toBeTruthy();
});

test("제공사 목록을 못 불러와도 표는 보이고 주소의 제공사 선택은 유지한다", async () => {
  stubModelsApi({ providers: { status: 500, body: { detail: "boom" } } });
  renderAt("/models?provider=openai");

  await screen.findByRole("table", { name: TABLE });

  expect((providerSelect() as HTMLSelectElement).value).toBe("openai");
  expect(optionLabels(providerSelect())).toEqual(["Provider 전체", "openai"]);
});
