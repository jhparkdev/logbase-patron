// @vitest-environment jsdom
import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeAll, expect, test, vi } from "vitest";
import { stubModelsApi, TEST_RESULT } from "../../test/modelsApi";
import { renderAt } from "../../test/renderAt";

const TABLE = "등록된 AI 모델";
const DIALOG = "연결 테스트";

beforeAll(() => {
  HTMLDialogElement.prototype.showModal = function () {
    this.open = true;
  };
  HTMLDialogElement.prototype.close = function () {
    this.open = false;
  };
});

afterEach(() => vi.restoreAllMocks());

async function openFromPanel() {
  renderAt("/models?model=3");
  const panel = within(
    await screen.findByRole("dialog", { name: "GPT-4o mini" }),
  );
  fireEvent.click(panel.getByRole("button", { name: DIALOG }));
  return within(screen.getByRole("dialog", { name: DIALOG }));
}

function runTest(dialog: ReturnType<typeof within>, prompt?: string) {
  if (prompt !== undefined) {
    fireEvent.change(dialog.getByLabelText("테스트 Prompt (선택)"), {
      target: { value: prompt },
    });
  }
  fireEvent.click(dialog.getByRole("button", { name: "테스트 실행" }));
}

const posts = (requests: { url: URL; method: string; body: unknown }[]) =>
  requests.filter(({ method }) => method === "POST");

test("패널의 연결 테스트 버튼은 Prompt 입력 칸과 비용 안내가 있는 창을 열고 아직 요청하지 않는다", async () => {
  const { requests } = stubModelsApi();
  const dialog = await openFromPanel();

  expect(dialog.getByLabelText("테스트 Prompt (선택)")).toBeTruthy();
  expect(dialog.getByText(/비용이 발생해요/)).toBeTruthy();
  expect(posts(requests)).toHaveLength(0);
});

test("실행하면 입력한 Prompt를 보내고 결과를 같은 창에 보여 준다", async () => {
  const { requests } = stubModelsApi();
  const dialog = await openFromPanel();

  runTest(dialog, "  안녕하세요  ");

  expect(await dialog.findByText("성공")).toBeTruthy();
  expect(posts(requests)).toHaveLength(1);
  expect(posts(requests)[0].url.pathname).toBe("/api/models/3/test");
  expect(posts(requests)[0].body).toEqual({ prompt: "안녕하세요" });
  expect(dialog.getByText("2026-11-01 12:00:00")).toBeTruthy();
  expect(dialog.getByText("1,234 ms")).toBeTruthy();
  expect(dialog.getByText("12")).toBeTruthy();
  expect(dialog.getByText("30")).toBeTruthy();
  expect(dialog.getByText("0.0004")).toBeTruthy();
  expect(dialog.getByText("OpenAI")).toBeTruthy();
  expect(dialog.queryByRole("button", { name: "테스트 실행" })).toBeNull();
});

test("Prompt를 비워도 실행할 수 있다", async () => {
  const { requests } = stubModelsApi();
  const dialog = await openFromPanel();

  runTest(dialog);

  await dialog.findByText("성공");
  expect(posts(requests)[0].body).toEqual({ prompt: "" });
});

test("실패한 테스트는 오류 문구를 보여 주고 비용은 0이 아니라 미확인이다", async () => {
  stubModelsApi({
    test: {
      status: 200,
      body: {
        ...TEST_RESULT,
        status: "FAILED",
        latency_ms: null,
        input_tokens: null,
        output_tokens: null,
        cost_usd: null,
        cost_status: "UNKNOWN",
        actual_provider: null,
        error_type: "AUTH_ERROR",
        error_message: "인증에 실패했어요.",
      },
    },
  });
  const dialog = await openFromPanel();

  runTest(dialog);

  expect(await dialog.findByText("실패")).toBeTruthy();
  expect(dialog.getByText("인증에 실패했어요.")).toBeTruthy();
  expect(dialog.getAllByText("미확인").length).toBeGreaterThan(0);
  expect(dialog.queryByText("0.0000")).toBeNull();
});

test("Prompt 칸 아래에 지금 글자 수를 한도와 함께 보여 준다", async () => {
  stubModelsApi();
  const dialog = await openFromPanel();
  expect(dialog.getByText("0/1000")).toBeTruthy();

  fireEvent.change(dialog.getByLabelText("테스트 Prompt (선택)"), {
    target: { value: "안녕하세요" },
  });

  expect(dialog.getByText("5/1000")).toBeTruthy();
});

test("글자 수는 저장될 값처럼 앞뒤 공백을 빼고 센다", async () => {
  stubModelsApi();
  const dialog = await openFromPanel();

  fireEvent.change(dialog.getByLabelText("테스트 Prompt (선택)"), {
    target: { value: "  안녕  " },
  });

  expect(dialog.getByText("2/1000")).toBeTruthy();
});

test("한도를 넘으면 넘은 글자 수 그대로 보여 준다", async () => {
  stubModelsApi();
  const dialog = await openFromPanel();

  fireEvent.change(dialog.getByLabelText("테스트 Prompt (선택)"), {
    target: { value: "a".repeat(1001) },
  });

  expect(dialog.getByText("1001/1000")).toBeTruthy();
});

test("Prompt가 1000자를 넘으면 요청 없이 이유를 알린다", async () => {
  const { requests } = stubModelsApi();
  const dialog = await openFromPanel();

  runTest(dialog, "a".repeat(1001));

  expect(
    await dialog.findByText("Prompt는 1000자 이하로 입력해 주세요."),
  ).toBeTruthy();
  expect(posts(requests)).toHaveLength(0);
});

test("서버가 테스트를 거절하면 서버 문구를 보여 주고 다시 실행할 수 있게 둔다", async () => {
  stubModelsApi({
    test: {
      status: 503,
      body: {
        code: "OPENROUTER_KEY_MISSING",
        message: "OpenRouter Key가 설정되지 않아 연결 테스트를 할 수 없습니다.",
      },
    },
  });
  const dialog = await openFromPanel();

  runTest(dialog, "안녕");

  expect((await dialog.findByRole("alert")).textContent).toBe(
    "OpenRouter Key가 설정되지 않아 연결 테스트를 할 수 없습니다.",
  );
  expect(dialog.getByRole("button", { name: "테스트 실행" })).toBeTruthy();
});

test("테스트가 끝나면 상세와 목록을 다시 불러온다", async () => {
  const { requests } = stubModelsApi();
  const dialog = await openFromPanel();
  await screen.findByRole("table", { name: TABLE });
  const count = (path: string) =>
    requests.filter(({ url }) => url.pathname === path).length;
  const detailBefore = count("/api/models/3");
  const listBefore = count("/api/models");

  runTest(dialog);

  await waitFor(() => expect(count("/api/models/3")).toBe(detailBefore + 1));
  await waitFor(() => expect(count("/api/models")).toBe(listBefore + 1));
});

test("표의 테스트 버튼도 같은 창을 열고 그 모델로 요청한다", async () => {
  const { requests } = stubModelsApi();
  renderAt("/models");
  await screen.findByRole("table", { name: TABLE });

  fireEvent.click(
    screen.getByRole("button", { name: "Mistral Small 연결 테스트" }),
  );
  const dialog = within(screen.getByRole("dialog", { name: DIALOG }));
  runTest(dialog);

  await dialog.findByText("성공");
  expect(posts(requests)[0].url.pathname).toBe("/api/models/4/test");
  expect(screen.queryByRole("dialog", { name: "모델 상세" })).toBeNull();
});

test("닫기를 누르면 창이 닫힌다", async () => {
  stubModelsApi();
  const dialog = await openFromPanel();

  fireEvent.click(dialog.getByRole("button", { name: "닫기" }));

  await waitFor(() =>
    expect(screen.queryByRole("dialog", { name: DIALOG })).toBeNull(),
  );
});
