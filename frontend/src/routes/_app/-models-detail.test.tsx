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

test("기본 정보에 Model ID, 제공사, 지원 기능 태그, Context Length를 보여 준다", async () => {
  stubModelsApi();
  const panel = await openPanel("/models?model=3", "GPT-4o mini");

  expect(panel.getByText("openai/gpt-4o-mini")).toBeTruthy();
  expect(panel.getByText("openai")).toBeTruthy();
  expect(panel.getByText("지원 기능 · Context 128,000 토큰")).toBeTruthy();
  const tags = within(panel.getByRole("list", { name: "지원 기능" }));
  expect(tags.getByText("텍스트·이미지 → 텍스트")).toBeTruthy();
  expect(tags.getByText("JSON 스키마")).toBeTruthy();
  expect(tags.getByText("함수 호출")).toBeTruthy();
  expect(tags.getByText("Temperature 조절")).toBeTruthy();
  expect(tags.getByText("추론 강도 조절")).toBeTruthy();
  // 추론 강도만 받지 않는 모델
  expect(tags.getAllByText("미지원")).toHaveLength(1);
});

test("Context Length를 모르면 빈칸이나 0이 아니라 미확인으로 보여 준다", async () => {
  stubModelsApi({
    detail: {
      status: 200,
      body: { ...DETAIL, context_length: null },
    },
  });
  const panel = await openPanel("/models?model=3", "GPT-4o mini");

  expect(panel.getByText("지원 기능 · Context 미확인")).toBeTruthy();
});

test("지원하지 않는 기능은 태그를 빼지 않고 미지원이라고 알린다", async () => {
  stubModelsApi({
    detail: {
      status: 200,
      body: {
        ...DETAIL,
        supports_json_schema: false,
        supports_tools: false,
        temperature_supported: false,
      },
    },
  });
  const panel = await openPanel("/models?model=3", "GPT-4o mini");

  const tags = within(panel.getByRole("list", { name: "지원 기능" }));
  expect(tags.getAllByText("미지원")).toHaveLength(4);
  expect(tags.getByText("JSON 스키마")).toBeTruthy();
});

test("표시 이름과 용도는 연필을 누를 때만 입력 칸이 된다", async () => {
  stubModelsApi();
  const panel = await openPanel("/models?model=3", "GPT-4o mini");

  expect(panel.queryByLabelText("표시 이름")).toBeNull();
  fireEvent.click(panel.getByRole("button", { name: "표시 이름 수정" }));

  expect((panel.getByLabelText("표시 이름") as HTMLInputElement).value).toBe(
    "GPT-4o mini",
  );
  expect(panel.getByRole("button", { name: "저장" })).toBeTruthy();
});

test("단가는 Input과 Output을 나눠 100만 토큰당으로 보여 주고 최종 확인 시각을 KST로 알린다", async () => {
  stubModelsApi();
  const panel = await openPanel("/models?model=3", "GPT-4o mini");

  expect(panel.getByText("0.15")).toBeTruthy();
  expect(panel.getByText("2.50")).toBeTruthy();
  expect(panel.getByText("최종 확인 2026-10-31 09:00:00")).toBeTruthy();
});

test("가격이 없으면 단가는 미확인이고 최종 확인은 없음이다", async () => {
  stubModelsApi({ detail: { status: 200, body: UNPRICED_DETAIL } });
  const panel = await openPanel("/models?model=4", "Mistral Small");

  // 단가 Input·Output 두 칸이 미확인
  expect(panel.getAllByText("미확인")).toHaveLength(2);
  expect(panel.queryByText("0.00")).toBeNull();
  expect(panel.getByText("최종 확인 없음")).toBeTruthy();
});

test("연결 테스트 카드는 마지막 테스트 시각과 결과, 마지막 성공 시각을 보여 준다", async () => {
  stubModelsApi();
  const panel = await openPanel("/models?model=3", "GPT-4o mini");

  expect(panel.getByText("2026-10-31 14:32:21")).toBeTruthy();
  expect(panel.getByText("성공")).toBeTruthy();
  expect(panel.getByText(/마지막 성공 2026-10-30 11:00:00/)).toBeTruthy();
});

test("패널을 열면 이번 테스트 숫자 네 칸은 비어 있고 실행하면 보인다고 안내한다", async () => {
  stubModelsApi();
  const panel = await openPanel("/models?model=3", "GPT-4o mini");

  expect(panel.getAllByText("—")).toHaveLength(4);
  expect(
    panel.getByText(/연결 테스트를 실행하면 이번 결과가 표시돼요\./),
  ).toBeTruthy();
});

test("테스트한 적이 없으면 미실행이고 마지막 성공은 없음이다", async () => {
  stubModelsApi({ detail: { status: 200, body: UNPRICED_DETAIL } });
  const panel = await openPanel("/models?model=4", "Mistral Small");

  expect(panel.getByText("미실행")).toBeTruthy();
  expect(panel.getByText(/마지막 성공 없음/)).toBeTruthy();
});

test("운영 상태는 현재 상태가 선택된 칸, 누르면 생기는 일, 활성화·비활성화 시각을 보여 준다", async () => {
  stubModelsApi();
  const panel = await openPanel("/models?model=3", "GPT-4o mini");

  expect(
    panel.getByRole("button", { name: "사용 중", pressed: true }),
  ).toBeTruthy();
  expect(
    panel.getByText(/을 누르면 새 시뮬레이션에서 이 모델이 빠져요/),
  ).toBeTruthy();
  expect(
    panel.getByText("활성화 2026-10-20 10:00:00 · 비활성화 없음"),
  ).toBeTruthy();
  expect(panel.getByText("마지막 수정 2026-10-31 14:32:21")).toBeTruthy();
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
