// @vitest-environment jsdom
import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeAll, expect, test, vi } from "vitest";
import { LIST, stubModelsApi } from "../../test/modelsApi";
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

function rowOf(name: string) {
  return within(screen.getByRole("table", { name: TABLE }))
    .getByText(name)
    .closest("tr") as HTMLElement;
}

test("주소의 조회 조건을 목록 요청에 담아 보낸다", async () => {
  const { requests } = stubModelsApi();
  renderAt("/models?q=gpt&sort=price_input&order=desc&page=2");

  await screen.findByRole("table", { name: TABLE });

  const params = requests[0].url.searchParams;
  expect(requests[0].url.pathname).toBe("/api/models");
  expect(Object.fromEntries(params)).toEqual({
    q: "gpt",
    sort: "price_input",
    order: "desc",
    page: "2",
    page_size: "10",
  });
});

test("조건이 없으면 정렬을 보내지 않아 서버 기본 정렬을 따른다", async () => {
  const { requests } = stubModelsApi();
  renderAt("/models");

  await screen.findByRole("table", { name: TABLE });

  expect(Object.fromEntries(requests[0].url.searchParams)).toEqual({
    page: "1",
    page_size: "10",
  });
});

test("서버가 준 모델을 칸마다 보여 주고 전체 개수를 알린다", async () => {
  stubModelsApi();
  renderAt("/models");

  await screen.findByRole("table", { name: TABLE });
  const row = within(rowOf("GPT-4o mini"));

  expect(row.getByText("openai/gpt-4o-mini")).toBeTruthy();
  expect(row.getByText("openai")).toBeTruthy();
  expect(row.getByText("텍스트, 이미지")).toBeTruthy();
  expect(row.getByText("0.15")).toBeTruthy();
  expect(row.getByText("2.50")).toBeTruthy();
  expect(row.getByText("사용 중")).toBeTruthy();
  expect(row.getByText("2026-10-31 14:32:21")).toBeTruthy();
  expect(row.getByText("성공")).toBeTruthy();
  expect(screen.getByText("12")).toBeTruthy();
});

test("가격이 없으면 0이 아니라 미확인으로 보여 준다", async () => {
  stubModelsApi();
  renderAt("/models");

  await screen.findByRole("table", { name: TABLE });
  const row = within(rowOf("Mistral Small"));

  expect(row.getAllByText("미확인")).toHaveLength(2);
  expect(row.queryByText("0.00")).toBeNull();
  expect(row.getByText("검증 중")).toBeTruthy();
});

test("한쪽 단가만 없으면 그 칸만 미확인이다", async () => {
  const [first] = LIST.items;
  const price = first.current_price;
  if (price === null) throw new Error("테스트 자료가 잘못되었다");
  stubModelsApi({
    list: {
      status: 200,
      body: {
        ...LIST,
        items: [
          {
            ...first,
            current_price: { ...price, output_price_per_token: null },
          },
        ],
      },
    },
  });
  renderAt("/models");

  await screen.findByRole("table", { name: TABLE });
  const row = within(rowOf("GPT-4o mini"));

  expect(row.getAllByText("미확인")).toHaveLength(1);
  expect(row.getByText("0.15")).toBeTruthy();
});

test("테스트한 적이 없으면 미실행으로 알린다", async () => {
  stubModelsApi();
  renderAt("/models");

  await screen.findByRole("table", { name: TABLE });

  expect(within(rowOf("Mistral Small")).getByText("미실행")).toBeTruthy();
});

test("실패한 연결 테스트도 결과 글자를 보여 준다", async () => {
  const [first] = LIST.items;
  stubModelsApi({
    list: {
      status: 200,
      body: {
        ...LIST,
        items: [{ ...first, last_test_status: "TIMEOUT" }],
      },
    },
  });
  renderAt("/models");

  await screen.findByRole("table", { name: TABLE });

  expect(within(rowOf("GPT-4o mini")).getByText("시간 초과")).toBeTruthy();
});

test("머리글을 누르면 정렬 조건을 주소에 남기고 서버에 다시 요청한다", async () => {
  const { requests } = stubModelsApi();
  const router = renderAt("/models?page=3");
  await screen.findByRole("table", { name: TABLE });

  fireEvent.click(screen.getByRole("button", { name: /Model ID/ }));

  await waitFor(() =>
    expect(routeMatch(router, ROUTE_ID)?.search).toEqual({
      sort: "openrouter_model_id",
      order: "asc",
    }),
  );
  await waitFor(() => {
    const last = requests[requests.length - 1].url.searchParams;
    expect(last.get("sort")).toBe("openrouter_model_id");
    expect(last.get("order")).toBe("asc");
    expect(last.get("page")).toBe("1");
  });
});

test("페이지를 옮기면 그 페이지를 요청한다", async () => {
  const { requests } = stubModelsApi();
  const router = renderAt("/models");
  await screen.findByRole("table", { name: TABLE });

  fireEvent.click(screen.getByRole("button", { name: "2" }));

  await waitFor(() =>
    expect(routeMatch(router, ROUTE_ID)?.search.page).toBe(2),
  );
  await waitFor(() =>
    expect(requests[requests.length - 1].url.searchParams.get("page")).toBe(
      "2",
    ),
  );
});

test("표시 이름을 누르면 그 모델의 상세 패널을 연다", async () => {
  stubModelsApi();
  const router = renderAt("/models?q=gpt");
  await screen.findByRole("table", { name: TABLE });

  fireEvent.click(screen.getByRole("link", { name: "GPT-4o mini" }));

  await waitFor(() =>
    expect(routeMatch(router, ROUTE_ID)?.search).toEqual({
      q: "gpt",
      model: 3,
    }),
  );
});

test("검색어에 맞는 모델이 없으면 조건에 맞는 모델이 없다고 알린다", async () => {
  stubModelsApi({ list: { status: 200, body: EMPTY_PAGE } });
  renderAt("/models?q=zzz");

  expect(await screen.findByText("조건에 맞는 모델이 없어요")).toBeTruthy();
});

test("등록된 모델이 없으면 그렇게 알린다", async () => {
  stubModelsApi({ list: { status: 200, body: EMPTY_PAGE } });
  renderAt("/models");

  expect(await screen.findByText("등록된 모델이 없어요")).toBeTruthy();
});

test("목록을 불러오지 못하면 알리고 다시 시도하면 불러온다", async () => {
  const { replies } = stubModelsApi({
    list: { status: 500, body: { detail: "boom" } },
  });
  renderAt("/models");

  expect(await screen.findByText("모델 목록을 불러오지 못했어요")).toBeTruthy();
  expect(screen.queryByText("boom")).toBeNull();

  replies.list = { status: 200, body: LIST };
  fireEvent.click(screen.getByRole("button", { name: "다시 시도" }));

  expect(await screen.findByRole("table", { name: TABLE })).toBeTruthy();
});
