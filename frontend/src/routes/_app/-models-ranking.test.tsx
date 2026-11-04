// @vitest-environment jsdom
import { fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeAll, expect, test, vi } from "vitest";
import { RANKING, stubModelsApi } from "../../test/modelsApi";
import { renderAt } from "../../test/renderAt";

const RANKING_PATH = /\/execution-providers\/ranking$/;

beforeAll(() => {
  HTMLDialogElement.prototype.showModal = function () {
    this.open = true;
  };
});

afterEach(() => vi.restoreAllMocks());

const rankingRequests = (requests: { url: URL }[]) =>
  requests.filter(({ url }) => RANKING_PATH.test(url.pathname));

test("상세 패널에서 업체를 싼 순서로 보여 주고 가장 싼 곳과 캐시 지원을 표시한다", async () => {
  stubModelsApi({ ranking: { status: 200, body: RANKING } });
  renderAt("/models?model=3");

  expect(await screen.findByText("추천 서버 업체")).toBeTruthy();
  expect(await screen.findByText("DeepInfra")).toBeTruthy();
  expect(screen.getByText("Parasail")).toBeTruthy();
  expect(screen.getByText("0.0021")).toBeTruthy();
  expect(screen.getByText("가장 저렴")).toBeTruthy();
  expect(screen.getByText("캐시 지원")).toBeTruthy();
  const names = screen
    .getAllByRole("listitem")
    .map((item) => item.textContent ?? "")
    .filter((text) => text.includes("DeepInfra") || text.includes("Parasail"));
  expect(names[0]).toContain("DeepInfra");
  expect(names[1]).toContain("Parasail");
});

test("가정한 토큰 수와 캐시 비율로 서버에 요청한다", async () => {
  const { requests } = stubModelsApi({
    ranking: { status: 200, body: RANKING },
  });
  renderAt("/models?model=3");
  await screen.findByText("DeepInfra");

  const [request] = rankingRequests(requests);
  expect(request.url.pathname).toBe(
    "/api/models/3/execution-providers/ranking",
  );
  expect(Object.fromEntries(request.url.searchParams)).toEqual({
    input_tokens: "1000",
    output_tokens: "500",
    cache_hit_ratio: "0.5",
  });
  expect(
    screen.getByText(
      "입력 1,000 · 출력 500 토큰으로 작업 한 번을 처리할 때의 예상 비용이에요.",
    ),
  ).toBeTruthy();
});

test("캐시 가정을 바꾸면 그 비율로 다시 요청한다", async () => {
  const { requests } = stubModelsApi({
    ranking: { status: 200, body: RANKING },
  });
  renderAt("/models?model=3");
  await screen.findByText("DeepInfra");

  fireEvent.change(screen.getByLabelText("캐시 가정"), {
    target: { value: "0" },
  });

  await waitFor(() => {
    const last = rankingRequests(requests).at(-1);
    expect(last?.url.searchParams.get("cache_hit_ratio")).toBe("0");
  });
});

test("순위에서 빠진 업체와 이유를 알린다", async () => {
  stubModelsApi({ ranking: { status: 200, body: RANKING } });
  renderAt("/models?model=3");

  expect(
    await screen.findByText("제외된 업체 1곳: Io Net(가동률 낮음)"),
  ).toBeTruthy();
});

test("비교할 업체가 없으면 그렇게 알린다", async () => {
  stubModelsApi();
  renderAt("/models?model=3");

  expect(await screen.findByText("비교할 수 있는 업체가 없어요")).toBeTruthy();
});

test("업체를 불러오지 못하면 그 구역만 알리고 다른 구역은 그대로 보인다", async () => {
  stubModelsApi({
    ranking: {
      status: 502,
      body: { code: "EXECUTION_PROVIDERS_UNAVAILABLE", message: "실패" },
    },
  });
  renderAt("/models?model=3");

  expect(await screen.findByText("추천 업체를 불러오지 못했어요")).toBeTruthy();
  expect(screen.getByText("기본 정보")).toBeTruthy();
});
