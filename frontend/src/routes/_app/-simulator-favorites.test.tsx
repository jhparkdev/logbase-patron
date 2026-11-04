// @vitest-environment jsdom
import { fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeAll, expect, test, vi } from "vitest";
import { renderAt } from "../../test/renderAt";
import {
  ACTIVE_MODEL,
  EXECUTION_PROVIDERS,
  RERUN_DRAFT,
  RUN_DETAIL,
  RUN_ID,
  SCENARIOS,
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

const JSON_HEADERS = { "Content-Type": "application/json" };
const SAVED_AT = "2026-11-04T01:00:00Z";
const DEEPINFRA = {
  model_id: ACTIVE_MODEL.model_id,
  execution_provider: "DeepInfra",
  created_at: SAVED_AT,
};
const DEEPINFRA_STAR = "Mistral Nemo · DeepInfra 즐겨찾기";
const DEKALLM_STAR = "Mistral Nemo · DekaLLM 즐겨찾기";
type Reply = { status: number; body?: unknown };

type Favorite = typeof DEEPINFRA;

/** P-04와 즐겨찾기 API 응답. 즐겨찾기는 등록·해제한 결과를 다음 조회에 돌려준다. */
function stub(overrides: Record<string, Reply> = {}) {
  const requests: { method: string; url: URL; request: Request }[] = [];
  let saved: Favorite[] = [DEEPINFRA];
  const sameKey = (a: Omit<Favorite, "created_at">) => (b: Favorite) =>
    a.model_id === b.model_id && a.execution_provider === b.execution_provider;
  const routes = async (request: Request, url: URL): Promise<Reply> => {
    const path = url.pathname;
    const key = `${request.method} ${path}`;
    if (overrides[key]) return overrides[key];
    if (key === "GET /api/model-favorites")
      return { status: 200, body: { items: saved } };
    if (key === "POST /api/model-favorites") {
      const item = { ...(await request.json()), created_at: SAVED_AT };
      saved = [item, ...saved.filter((other) => !sameKey(item)(other))];
      return { status: 201, body: item };
    }
    if (key === "DELETE /api/model-favorites") {
      const target = {
        model_id: Number(url.searchParams.get("model_id")),
        execution_provider: url.searchParams.get("execution_provider") ?? "",
      };
      saved = saved.filter((other) => !sameKey(target)(other));
      return { status: 204 };
    }
    if (key === "GET /api/models")
      return {
        status: 200,
        body: { items: [ACTIVE_MODEL], page: 1, page_size: 100, total: 1 },
      };
    if (key === "GET /api/scenarios") return { status: 200, body: SCENARIOS };
    if (path.endsWith("/execution-providers"))
      return { status: 200, body: EXECUTION_PROVIDERS };
    if (key === "GET /api/simulations/images/limits")
      return {
        status: 200,
        body: { max_count: 4, max_bytes: 5_242_880, mime_types: ["image/png"] },
      };
    if (path.endsWith("/rerun-draft"))
      return { status: 200, body: RERUN_DRAFT };
    return { status: 200, body: RUN_DETAIL };
  };
  vi.stubGlobal("fetch", async (request: Request) => {
    const url = new URL(request.url);
    requests.push({ method: request.method, url, request: request.clone() });
    const reply = await routes(request, url);
    return new Response(
      reply.body === undefined ? null : JSON.stringify(reply.body),
      { status: reply.status, headers: JSON_HEADERS },
    );
  });
  const find = (method: string) =>
    requests.filter(
      (item) =>
        item.method === method && item.url.pathname === "/api/model-favorites",
    );
  return { find };
}

async function openPicker() {
  const button = await screen.findByRole("button", { name: "모델 검색" });
  await waitFor(() => expect(button.hasAttribute("disabled")).toBe(false));
  fireEvent.click(button);
}

async function star(name: string) {
  const button = await screen.findByRole("button", { name });
  await waitFor(() => expect(button.hasAttribute("disabled")).toBe(false));
  return button;
}

test("저장된 즐겨찾기를 켜 두고, 누르면 바로 켜며 모델·Provider를 저장한다", async () => {
  const api = stub();
  renderAt("/simulator");
  await openPicker();
  expect((await star(DEEPINFRA_STAR)).getAttribute("aria-pressed")).toBe(
    "true",
  );
  const dekaLLM = await star(DEKALLM_STAR);
  expect(dekaLLM.getAttribute("aria-pressed")).toBe("false");

  fireEvent.click(dekaLLM);
  await waitFor(() =>
    expect(
      screen
        .getByRole("button", { name: DEKALLM_STAR })
        .getAttribute("aria-pressed"),
    ).toBe("true"),
  );
  await waitFor(() => expect(api.find("POST")).toHaveLength(1));
  expect(await api.find("POST")[0].request.json()).toEqual({
    model_id: ACTIVE_MODEL.model_id,
    execution_provider: "DekaLLM",
  });
});

test("켜진 별을 누르면 그 조합만 해제한다", async () => {
  const api = stub();
  renderAt("/simulator");
  await openPicker();
  fireEvent.click(await star(DEEPINFRA_STAR));
  await waitFor(() => expect(api.find("DELETE")).toHaveLength(1));
  const params = api.find("DELETE")[0].url.searchParams;
  expect(params.get("model_id")).toBe(String(ACTIVE_MODEL.model_id));
  expect(params.get("execution_provider")).toBe("DeepInfra");
  await waitFor(() =>
    expect(
      screen
        .getByRole("button", { name: DEEPINFRA_STAR })
        .getAttribute("aria-pressed"),
    ).toBe("false"),
  );
});

test("저장에 실패하면 그 항목만 되돌리고 다시 누르라고 안내한다", async () => {
  stub({
    "POST /api/model-favorites": {
      status: 500,
      body: { code: "INTERNAL_ERROR", message: "오류" },
    },
  });
  renderAt("/simulator");
  await openPicker();
  fireEvent.click(await star(DEKALLM_STAR));
  expect(
    await screen.findByText("즐겨찾기를 바꾸지 못했어요. 다시 눌러 주세요."),
  ).toBeDefined();
  expect(
    screen
      .getByRole("button", { name: DEKALLM_STAR })
      .getAttribute("aria-pressed"),
  ).toBe("false");
  expect(
    screen
      .getByRole("button", { name: DEEPINFRA_STAR })
      .getAttribute("aria-pressed"),
  ).toBe("true");
});

test("즐겨찾기를 불러오지 못해도 모델은 고를 수 있고 즐겨찾기만 다시 시도하게 한다", async () => {
  const api = stub({
    "GET /api/model-favorites": {
      status: 500,
      body: { code: "INTERNAL_ERROR", message: "오류" },
    },
  });
  renderAt("/simulator");
  await openPicker();
  expect(
    await screen.findByRole("checkbox", { name: "Mistral Nemo · DeepInfra" }),
  ).toBeDefined();
  fireEvent.click(screen.getByRole("button", { name: "즐겨찾기 목록" }));
  fireEvent.click(await screen.findByRole("button", { name: "다시 시도" }));
  await waitFor(() => expect(api.find("GET")).toHaveLength(2));
});

test("재실행 화면에서도 즐겨찾기를 쓸 수 있다", async () => {
  const api = stub();
  renderAt(`/simulator?sourceRun=${RUN_ID}`);
  await openPicker();
  fireEvent.click(await star(DEKALLM_STAR));
  await waitFor(() => expect(api.find("POST")).toHaveLength(1));
});
