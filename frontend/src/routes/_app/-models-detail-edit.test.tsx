// @vitest-environment jsdom
import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeAll, expect, test, vi } from "vitest";
import { DETAIL, stubModelsApi } from "../../test/modelsApi";
import { renderAt } from "../../test/renderAt";

const TABLE = "등록된 AI 모델";

beforeAll(() => {
  HTMLDialogElement.prototype.showModal = function () {
    this.open = true;
  };
});

afterEach(() => vi.restoreAllMocks());

type Panel = ReturnType<typeof within>;

async function openPanel(name = "GPT-4o mini") {
  renderAt("/models?model=3");
  return within(await screen.findByRole("dialog", { name }));
}

const pencil = (panel: Panel, label: string) =>
  panel.getByRole("button", { name: `${label} 수정` });

function startEdit(panel: Panel, label: string) {
  fireEvent.click(pencil(panel, label));
  return panel.getByRole("textbox", { name: label }) as HTMLInputElement;
}

function typeAndSave(input: HTMLInputElement, panel: Panel, value: string) {
  fireEvent.change(input, { target: { value } });
  fireEvent.click(panel.getByRole("button", { name: "저장" }));
}

const patches = (requests: { url: URL; method: string; body: unknown }[]) =>
  requests.filter(({ method }) => method === "PATCH");

test("처음에는 입력 칸과 저장 버튼 없이 글자와 연필만 보인다", async () => {
  stubModelsApi({
    detail: { status: 200, body: { ...DETAIL, purpose: "상품 설명 생성" } },
  });
  const panel = await openPanel();

  expect(panel.getByText("상품 설명 생성")).toBeTruthy();
  expect(pencil(panel, "표시 이름")).toBeTruthy();
  expect(pencil(panel, "용도")).toBeTruthy();
  expect(panel.queryByRole("textbox")).toBeNull();
  expect(panel.queryByRole("button", { name: "저장" })).toBeNull();
});

test("용도가 비어 있으면 미입력으로 보여 준다", async () => {
  stubModelsApi({
    detail: { status: 200, body: { ...DETAIL, purpose: null } },
  });
  const panel = await openPanel();

  expect(panel.getByText("미입력")).toBeTruthy();
});

test("연필을 누르면 그 항목만 현재 값이 채워진 입력 칸과 취소·저장 버튼으로 바뀐다", async () => {
  stubModelsApi();
  const panel = await openPanel();

  const input = startEdit(panel, "표시 이름");

  expect(input.value).toBe("GPT-4o mini");
  expect(panel.getByRole("button", { name: "취소" })).toBeTruthy();
  expect(panel.getByRole("button", { name: "저장" })).toBeTruthy();
  expect(panel.queryByRole("button", { name: "표시 이름 수정" })).toBeNull();
  // 다른 항목은 그대로
  expect(pencil(panel, "용도")).toBeTruthy();
});

test("저장하면 바뀐 항목만 보내고, 응답으로 제목을 바꾸며, 글자 보기로 돌아가고, 목록을 다시 불러온다", async () => {
  const { requests } = stubModelsApi({
    update: { status: 200, body: { ...DETAIL, display_name: "새 이름" } },
  });
  const panel = await openPanel();
  await screen.findByRole("table", { name: TABLE });
  const listRequests = () =>
    requests.filter(({ url }) => url.pathname === "/api/models").length;
  const before = listRequests();

  typeAndSave(startEdit(panel, "표시 이름"), panel, "  새 이름  ");

  expect(await screen.findByRole("dialog", { name: "새 이름" })).toBeTruthy();
  expect(patches(requests)).toHaveLength(1);
  expect(patches(requests)[0].url.pathname).toBe("/api/models/3");
  expect(patches(requests)[0].body).toEqual({ display_name: "새 이름" });
  await waitFor(() => expect(panel.queryByRole("textbox")).toBeNull());
  expect(panel.queryByRole("button", { name: "저장" })).toBeNull();
  expect(pencil(panel, "표시 이름")).toBeTruthy();
  await waitFor(() => expect(listRequests()).toBe(before + 1));
});

test("용도를 비우고 저장하면 빈 글자를 보내 용도를 지우고 미입력으로 돌아간다", async () => {
  const { requests } = stubModelsApi({
    detail: { status: 200, body: { ...DETAIL, purpose: "요약" } },
    update: { status: 200, body: { ...DETAIL, purpose: null } },
  });
  const panel = await openPanel();

  typeAndSave(startEdit(panel, "용도"), panel, "");

  expect(await panel.findByText("미입력")).toBeTruthy();
  expect(patches(requests)[0].body).toEqual({ purpose: "" });
});

test("취소하면 요청 없이 글자 보기로 돌아가고, 다시 열면 저장된 값이 채워진다", async () => {
  const { requests } = stubModelsApi();
  const panel = await openPanel();

  const input = startEdit(panel, "표시 이름");
  fireEvent.change(input, { target: { value: "버릴 이름" } });
  fireEvent.click(panel.getByRole("button", { name: "취소" }));

  expect(panel.queryByRole("textbox")).toBeNull();
  expect(patches(requests)).toHaveLength(0);
  expect(startEdit(panel, "표시 이름").value).toBe("GPT-4o mini");
});

test("표시 이름이 비어 있으면 요청 없이 이유를 알리고 수정 중으로 남는다", async () => {
  const { requests } = stubModelsApi();
  const panel = await openPanel();

  typeAndSave(startEdit(panel, "표시 이름"), panel, "   ");

  expect(await panel.findByText("표시 이름을 입력해 주세요.")).toBeTruthy();
  expect(patches(requests)).toHaveLength(0);
  expect(panel.getByRole("textbox", { name: "표시 이름" })).toBeTruthy();
});

test("서버가 거절하면 서버 문구를 보여 주고 입력은 그대로 둔 채 수정 중으로 남는다", async () => {
  stubModelsApi({
    update: {
      status: 422,
      body: {
        code: "VALIDATION_ERROR",
        message: "표시 이름이 올바르지 않아요.",
      },
    },
  });
  const panel = await openPanel();

  typeAndSave(startEdit(panel, "표시 이름"), panel, "새 이름");

  expect((await panel.findByRole("alert")).textContent).toBe(
    "표시 이름이 올바르지 않아요.",
  );
  expect(
    (panel.getByRole("textbox", { name: "표시 이름" }) as HTMLInputElement)
      .value,
  ).toBe("새 이름");
});

test("계약과 다른 오류 응답은 내부 내용 없이 일반 문구로 알린다", async () => {
  stubModelsApi({ update: { status: 500, body: { detail: "boom" } } });
  const panel = await openPanel();

  typeAndSave(startEdit(panel, "표시 이름"), panel, "새 이름");

  const alert = await panel.findByRole("alert");
  expect(alert.textContent).toBe(
    "요청을 처리하지 못했어요. 다시 시도해 주세요.",
  );
});
