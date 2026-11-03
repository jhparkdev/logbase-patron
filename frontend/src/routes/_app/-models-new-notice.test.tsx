// @vitest-environment jsdom
import { fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeAll, expect, test, vi } from "vitest";
import { NEW_MODELS, NO_NEW_MODELS, stubModelsApi } from "../../test/modelsApi";
import { renderAt } from "../../test/renderAt";

const TABLE = "등록된 AI 모델";
const NEW_PATH = "/api/models/openrouter/new";

beforeAll(() => {
  HTMLDialogElement.prototype.showModal = function () {
    this.open = true;
  };
});

afterEach(() => vi.restoreAllMocks());

test("새 모델이 있으면 개수와 기간, 가장 최근 모델 이름을 알린다", async () => {
  stubModelsApi({ newModels: { status: 200, body: NEW_MODELS } });
  renderAt("/models");

  expect(await screen.findByText("새 모델 5개가 올라왔어요")).toBeTruthy();
  expect(
    screen.getByText(
      "최근 30일 안에 올라왔어요. Acme: Alpha, Acme: Beta, Acme: Gamma 외 2개",
    ),
  ).toBeTruthy();
});

test("최근 30일과 최근 모델 몇 개만 서버에 요청한다", async () => {
  const { requests } = stubModelsApi({
    newModels: { status: 200, body: NEW_MODELS },
  });
  renderAt("/models");
  await screen.findByText("새 모델 5개가 올라왔어요");

  const request = requests.find(({ url }) => url.pathname === NEW_PATH);
  expect(Object.fromEntries(request?.url.searchParams ?? [])).toEqual({
    days: "30",
    limit: "3",
  });
});

test("등록하러 가기를 누르면 신규 모델 등록 패널이 열린다", async () => {
  stubModelsApi({ newModels: { status: 200, body: NEW_MODELS } });
  renderAt("/models");
  await screen.findByText("새 모델 5개가 올라왔어요");

  fireEvent.click(screen.getByRole("button", { name: "등록하러 가기" }));

  expect(
    await screen.findByRole("dialog", { name: "신규 모델 등록" }),
  ).toBeTruthy();
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
