// @vitest-environment jsdom
import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeAll, expect, test, vi } from "vitest";
import { DETAIL, stubModelsApi, UNPRICED_DETAIL } from "../../test/modelsApi";
import { renderAt } from "../../test/renderAt";

const NOT_FOUND = {
  status: 404,
  body: { code: "NOT_FOUND", message: "모델을 찾을 수 없습니다." },
};

beforeAll(() => {
  HTMLDialogElement.prototype.showModal = function () {
    this.open = true;
  };
});

afterEach(() => vi.restoreAllMocks());

/** 모델 이름이 제목이 되면 상세를 다 받은 것 */
async function openPanel(path: string, name: string) {
  renderAt(path);
  return within(await screen.findByRole("dialog", { name }));
}

test("주소의 모델 번호로 상세를 요청하고 표시 이름을 제목으로 보여 준다", async () => {
  const { requests } = stubModelsApi();
  await openPanel("/models?model=3", "GPT-4o mini");

  const detailRequest = requests.find(
    ({ url }) => url.pathname === "/api/models/3",
  );
  expect(detailRequest).toBeTruthy();
});

test("기본 정보에 Model ID, 제공사, 입출력 형식, 지원 여부, Context Length를 보여 준다", async () => {
  stubModelsApi();
  const panel = await openPanel("/models?model=3", "GPT-4o mini");

  expect(panel.getByText("openai/gpt-4o-mini")).toBeTruthy();
  expect(panel.getByText("openai")).toBeTruthy();
  expect(panel.getByText("텍스트, 이미지")).toBeTruthy();
  expect(panel.getAllByText("지원")).toHaveLength(2);
  expect(panel.getByText("128,000")).toBeTruthy();
});

test("Context Length를 모르면 빈칸이나 0이 아니라 미확인으로 보여 준다", async () => {
  stubModelsApi({
    detail: {
      status: 200,
      body: { ...DETAIL, context_length: null },
    },
  });
  const panel = await openPanel("/models?model=3", "GPT-4o mini");

  expect(panel.getByText("미확인")).toBeTruthy();
});

test("JSON·함수 호출을 지원하지 않으면 미지원으로 보여 준다", async () => {
  stubModelsApi({
    detail: {
      status: 200,
      body: { ...DETAIL, supports_json_schema: false, supports_tools: false },
    },
  });
  const panel = await openPanel("/models?model=3", "GPT-4o mini");

  expect(panel.getAllByText("미지원")).toHaveLength(2);
});

test("단가는 Input과 Output을 나눠 100만 토큰당으로 보여 주고 가격 확인 시각을 KST로 알린다", async () => {
  stubModelsApi();
  const panel = await openPanel("/models?model=3", "GPT-4o mini");

  expect(panel.getByText("0.15")).toBeTruthy();
  expect(panel.getByText("2.50")).toBeTruthy();
  expect(panel.getByText("2026-10-31 09:00:00")).toBeTruthy();
});

test("가격이 없으면 단가는 미확인이고 가격 확인 시각은 없음이다", async () => {
  stubModelsApi({ detail: { status: 200, body: UNPRICED_DETAIL } });
  const panel = await openPanel("/models?model=4", "Mistral Small");

  // 단가 Input·Output 두 칸이 미확인
  expect(panel.getAllByText("미확인")).toHaveLength(2);
  expect(panel.queryByText("0.00")).toBeNull();
  expect(panel.getByText("가격 확인 시각").nextSibling?.textContent).toBe(
    "없음",
  );
});

test("연결 테스트는 마지막 결과와 마지막 성공 시각을 보여 준다", async () => {
  stubModelsApi();
  const panel = await openPanel("/models?model=3", "GPT-4o mini");

  expect(panel.getByText("2026-10-31 14:32:21")).toBeTruthy();
  expect(panel.getByText("성공")).toBeTruthy();
  expect(panel.getByText("2026-10-30 11:00:00")).toBeTruthy();
});

test("테스트한 적이 없으면 미실행이고 성공 시각은 없음이다", async () => {
  stubModelsApi({ detail: { status: 200, body: UNPRICED_DETAIL } });
  const panel = await openPanel("/models?model=4", "Mistral Small");

  expect(panel.getByText("미실행")).toBeTruthy();
  expect(panel.getByText("마지막 성공 테스트").nextSibling?.textContent).toBe(
    "없음",
  );
});

test("운영 상태는 현재 상태와 활성화·비활성화 시각을 보여 준다", async () => {
  stubModelsApi();
  const panel = await openPanel("/models?model=3", "GPT-4o mini");

  expect(panel.getByText("사용 중")).toBeTruthy();
  expect(panel.getByText("2026-10-20 10:00:00")).toBeTruthy();
  expect(panel.getByText("비활성화 시각").nextSibling?.textContent).toBe(
    "없음",
  );
});

test("없는 모델 번호면 찾을 수 없다고 알리고 다시 시도는 두지 않는다", async () => {
  stubModelsApi({ detail: NOT_FOUND });
  renderAt("/models?model=999");

  const panel = within(
    await screen.findByRole("dialog", { name: "모델 상세" }),
  );
  expect(await panel.findByText("모델을 찾을 수 없어요")).toBeTruthy();
  expect(panel.queryByRole("button", { name: "다시 시도" })).toBeNull();
});

test("상세를 불러오지 못하면 알리고 다시 시도하면 불러온다", async () => {
  const { replies } = stubModelsApi({
    detail: { status: 500, body: { detail: "boom" } },
  });
  renderAt("/models?model=3");
  const panel = within(
    await screen.findByRole("dialog", { name: "모델 상세" }),
  );
  expect(await panel.findByText("모델 상세를 불러오지 못했어요")).toBeTruthy();
  expect(panel.queryByText("boom")).toBeNull();

  replies.detail = { status: 200, body: DETAIL };
  fireEvent.click(panel.getByRole("button", { name: "다시 시도" }));

  await waitFor(() =>
    expect(screen.getByRole("dialog", { name: "GPT-4o mini" })).toBeTruthy(),
  );
});
