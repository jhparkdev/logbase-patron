// @vitest-environment jsdom
import {
  createMemoryHistory,
  createRootRoute,
  createRouter,
  RouterContextProvider,
} from "@tanstack/react-router";
import {
  cleanup,
  fireEvent,
  render as renderDom,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, beforeAll, expect, test, vi } from "vitest";
import { createComparisons } from "../lib/comparisons";
import type { SimulatorDraft } from "../lib/form";
import { IMAGE_LIMITS, TEXT_LIMIT } from "../lib/limits";
import type { ModelChoice } from "../lib/presentation";
import { dbMock } from "./dbMock.fixture";
import { SimulatorPage } from "./SimulatorPage";

function render(ui: ReactNode) {
  const router = createRouter({
    routeTree: createRootRoute(),
    history: createMemoryHistory({ initialEntries: ["/"] }),
  });
  return renderDom(ui, {
    wrapper: ({ children }) => (
      <RouterContextProvider router={router}>{children}</RouterContextProvider>
    ),
  });
}

afterEach(cleanup);
beforeAll(() => {
  HTMLDialogElement.prototype.showModal = function () {
    this.setAttribute("open", "");
  };
  HTMLDialogElement.prototype.close = function () {
    this.removeAttribute("open");
  };
});

const choices: ModelChoice[] = [
  {
    key: "a:p1",
    name: "모델 A",
    provider: "Provider 1",
    selectable: true,
    supportsImages: true,
    supportedParameters: ["temperature", "max_tokens"],
  },
  {
    key: "a:p2",
    name: "모델 A",
    provider: "Provider 2",
    selectable: true,
    supportsImages: true,
    supportedParameters: ["temperature", "max_tokens"],
  },
  {
    key: "b:p1",
    name: "모델 B",
    provider: "Provider 1",
    selectable: false,
    unavailableReason: "비활성 모델",
    supportsImages: false,
    supportedParameters: [],
  },
];
/** 추가 입력 칩을 켜야 그 입력 칸이 나온다. */
function openExtra(name: "입력 텍스트" | "이미지" | "JSON Schema") {
  const chip = screen.getByRole("button", { name: new RegExp(`^${name}`) });
  if (chip.getAttribute("aria-pressed") !== "true") fireEvent.click(chip);
}
function imageInput() {
  openExtra("이미지");
  return screen.getByLabelText("이미지 파일 추가");
}
function fill() {
  fireEvent.change(screen.getByLabelText("Prompt"), {
    target: { value: "요약해 주세요." },
  });
  fireEvent.click(screen.getByRole("button", { name: "모델 검색" }));
  fireEvent.click(
    screen.getByRole("checkbox", { name: "모델 A · Provider 1" }),
  );
  fireEvent.click(
    screen.getByRole("checkbox", { name: "모델 A · Provider 2" }),
  );
  fireEvent.click(screen.getByRole("button", { name: "선택 적용" }));
}

test("API 미연결 화면은 가짜 모델과 실행 결과를 만들지 않는다", () => {
  render(<SimulatorPage />);
  expect(
    screen.getByRole("button", { name: "비교 실행" }).hasAttribute("disabled"),
  ).toBe(true);
  expect(screen.getByText("아직 실행 결과가 없어요")).toBeDefined();
  expect(screen.queryByText("모델 A")).toBeNull();
});

test("공통 설정은 닫혀 있고, 기본값은 비어 있으며 접어도 편집값이 유지된다", () => {
  const onRun = vi.fn();
  render(<SimulatorPage choices={choices} onRun={onRun} />);
  const toggle = screen.getByRole("button", { name: /^공통 설정 선택사항$/ });
  expect(toggle.getAttribute("aria-expanded")).toBe("false");
  fireEvent.click(toggle);
  expect(screen.getByLabelText("공통 Temperature").getAttribute("value")).toBe(
    "",
  );
  fireEvent.change(screen.getByLabelText("공통 Temperature"), {
    target: { value: "0.7" },
  });
  expect(
    (
      screen.getByRole("slider", {
        name: "공통 Temperature 조절",
      }) as HTMLInputElement
    ).value,
  ).toBe("0.7");
  fireEvent.change(
    screen.getByRole("slider", { name: "공통 Temperature 조절" }),
    {
      target: { value: "1.2" },
    },
  );
  expect(
    (screen.getByLabelText("공통 Temperature") as HTMLInputElement).value,
  ).toBe("1.2");
  fireEvent.click(toggle);
  fireEvent.click(toggle);
  expect(
    (screen.getByLabelText("공통 Temperature") as HTMLInputElement).value,
  ).toBe("1.2");
  expect(onRun).not.toHaveBeenCalled();
});

test("접힌 공통 설정의 오류를 펼쳐서 보여주고 제출한 뒤에만 검증한다", async () => {
  render(<SimulatorPage choices={choices} onRun={vi.fn()} />);
  fill();
  const toggle = screen.getByRole("button", { name: /^공통 설정 선택사항$/ });
  fireEvent.click(toggle);
  // 공통값은 공통 설정을 켰을 때만 검사한다
  fireEvent.click(screen.getByLabelText("공통 설정 사용"));
  fireEvent.change(screen.getByLabelText("공통 최대 출력 토큰"), {
    target: { value: "0" },
  });
  fireEvent.click(toggle);
  expect(screen.queryByRole("alert")).toBeNull();
  fireEvent.click(screen.getByRole("button", { name: "비교 실행" }));
  await waitFor(() =>
    expect(toggle.getAttribute("aria-expanded")).toBe("true"),
  );
  expect(screen.getByText("1 이상의 정수를 입력해 주세요.")).toBeDefined();
});

test("동일 모델의 서로 다른 Provider를 비교하며 확인 후 한 번만 제출한다", async () => {
  let finish: () => void = () => {};
  const onRun = vi.fn(
    (_draft: SimulatorDraft) =>
      new Promise<void>((resolve) => {
        finish = resolve;
      }),
  );
  render(<SimulatorPage choices={choices} onRun={onRun} />);
  fill();
  fireEvent.click(screen.getByRole("button", { name: "비교 실행" }));
  const dialog = await screen.findByRole("dialog", {
    name: "비교를 실행할까요?",
  });
  expect(onRun).not.toHaveBeenCalled();
  const confirm = within(dialog).getByRole("button", { name: "실행하기" });
  fireEvent.click(confirm);
  fireEvent.click(confirm);
  await waitFor(() => expect(onRun).toHaveBeenCalledTimes(1));
  expect(onRun.mock.calls[0]?.[0]).toMatchObject({
    comparisons: createComparisons(["a:p1", "a:p2"]).map((item) => ({
      comparisonId: expect.any(String),
      modelKey: item.modelKey,
    })),
    temperature: undefined,
  });
  expect(
    screen
      .getByRole("button", { name: "실행 요청 중" })
      .hasAttribute("disabled"),
  ).toBe(true);
  finish();
  await waitFor(() =>
    expect(screen.getByRole("button", { name: "비교 실행" })).toBeDefined(),
  );
  expect(screen.getByText("아직 실행 결과가 없어요")).toBeDefined();
});

test("네 모델이 선택되어 있어도 검색으로 교체할 수 있고 하나만 남으면 실행을 막는다", () => {
  const catalog = [
    ...choices,
    ...["c", "d"].map((name) => ({ ...choices[0], key: `${name}:p1`, name })),
  ];
  render(
    <SimulatorPage
      choices={catalog}
      onRun={vi.fn()}
      initialValues={{
        comparisons: createComparisons(["a:p1", "a:p2", "c:p1", "d:p1"]),
      }}
    />,
  );
  expect(
    screen.getByRole("button", { name: "모델 검색" }).hasAttribute("disabled"),
  ).toBe(false);
  fireEvent.click(screen.getByRole("button", { name: "비교 모델 4 제거" }));
  fireEvent.click(screen.getByRole("button", { name: "비교 모델 3 제거" }));
  fireEvent.click(screen.getByRole("button", { name: "비교 모델 2 제거" }));
  expect(
    screen.getByRole("button", { name: "비교 실행" }).hasAttribute("disabled"),
  ).toBe(true);
});

test.each([1, 2])(
  "선택한 모델 두 개 중 %i번을 제거하면 실행·직접 제출을 막고 두 개로 복구하면 실행한다",
  async (removed) => {
    const onRun = vi.fn();
    render(<SimulatorPage choices={choices} onRun={onRun} />);
    fill();
    const run = screen.getByRole("button", { name: "비교 실행" });
    expect(run.hasAttribute("disabled")).toBe(false);

    fireEvent.click(
      screen.getByRole("button", { name: `비교 모델 ${removed} 제거` }),
    );
    expect(screen.queryByRole("heading", { name: /^비교 모델 2/ })).toBeNull();
    const remaining = removed === 1 ? "a:p2" : "a:p1";
    const selected = screen.getByRole("list", { name: "선택한 비교 모델" });
    expect(
      within(selected).getByText(removed === 1 ? "Provider 2" : "Provider 1"),
    ).toBeDefined();
    expect(run.hasAttribute("disabled")).toBe(true);
    expect(
      screen
        .getByRole("button", { name: "비교 모델 1 제거" })
        .hasAttribute("disabled"),
    ).toBe(true);
    fireEvent.click(run);
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(onRun).not.toHaveBeenCalled();

    fireEvent.submit(run.closest("form") as HTMLFormElement);
    await screen.findByText("비교 항목을 2개 이상 골라 주세요.");
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(onRun).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole("button", { name: "모델 검색" }));
    expect(run.hasAttribute("disabled")).toBe(true);
    const restored = removed === 1 ? "a:p1" : "a:p2";
    fireEvent.click(
      screen.getByRole("checkbox", {
        name: `모델 A · Provider ${removed === 1 ? 1 : 2}`,
      }),
    );
    fireEvent.click(screen.getByRole("button", { name: "선택 적용" }));
    expect(run.hasAttribute("disabled")).toBe(false);
    fireEvent.click(run);
    const dialog = await screen.findByRole("dialog", {
      name: "비교를 실행할까요?",
    });
    fireEvent.click(within(dialog).getByRole("button", { name: "실행하기" }));
    await waitFor(() => expect(onRun).toHaveBeenCalledTimes(1));
    expect(
      onRun.mock.calls[0]?.[0].comparisons.map(
        (item: SimulatorDraft["comparisons"][number]) => item.modelKey,
      ),
    ).toEqual([remaining, restored]);
  },
);

test("이미지가 필요한 시나리오만 선택지 이름 뒤에 괄호로 표시한다", () => {
  render(
    <SimulatorPage
      choices={dbMock.choices}
      scenarios={dbMock.scenarios}
      onRun={vi.fn()}
    />,
  );
  fireEvent.click(screen.getByRole("radio", { name: "기본 시나리오" }));
  expect(
    screen.getByRole("option", { name: "상품 이미지·속성 분석(이미지 필요)" }),
  ).toBeDefined();
  expect(
    screen.getByRole("option", { name: "상품 설명 및 마케팅 문구 생성" }),
  ).toBeDefined();
});

test("기존 DB 시나리오의 Prompt·Schema를 복원하고 공통 설정은 기본값을 따른다", () => {
  render(
    <SimulatorPage
      choices={dbMock.choices}
      scenarios={dbMock.scenarios}
      onRun={vi.fn()}
    />,
  );
  const scenario = dbMock.scenarios.find((item) => !item.imageRequired);
  if (!scenario) throw new Error("기존 mock 시나리오가 필요합니다.");
  fireEvent.click(screen.getByRole("radio", { name: "기본 시나리오" }));
  fireEvent.change(screen.getByLabelText("시나리오"), {
    target: { value: scenario.key },
  });
  expect((screen.getByLabelText("Prompt") as HTMLTextAreaElement).value).toBe(
    scenario.prompt,
  );
  openExtra("JSON Schema");
  expect(
    (screen.getByLabelText(/JSON Schema/) as HTMLTextAreaElement).value,
  ).toBe(scenario.schemaText);
  fireEvent.click(screen.getByRole("button", { name: /^공통 설정 선택사항$/ }));
  expect(
    (screen.getByLabelText("공통 Temperature") as HTMLInputElement).value,
  ).toBe("");
  fireEvent.change(screen.getByLabelText("공통 Temperature"), {
    target: { value: "0.3" },
  });
  fireEvent.click(screen.getByRole("button", { name: "기본 설정으로" }));
  expect(
    (screen.getByLabelText("공통 Temperature") as HTMLInputElement).value,
  ).toBe("");
  expect((screen.getByLabelText("Prompt") as HTMLTextAreaElement).value).toBe(
    scenario.prompt,
  );
});

test("이미지를 지원하지 않는 모델은 실행 전 안내한다", async () => {
  const onRun = vi.fn();
  render(
    <SimulatorPage
      choices={choices.map((item) => ({ ...item, supportsImages: false }))}
      onRun={onRun}
    />,
  );
  fill();
  fireEvent.change(imageInput(), {
    target: { files: [new File(["png"], "image.png", { type: "image/png" })] },
  });
  // 실행 전에도 카드가 충돌을 알리고, 실행하면 차단 사유로 막는다
  expect(
    screen.getAllByText(
      "이미지 입력을 지원하지 않아요. 이미지를 빼거나 모델을 바꿔 주세요.",
    ),
  ).toHaveLength(2);
  fireEvent.click(screen.getByRole("button", { name: "비교 실행" }));
  expect(
    await screen.findByText("모델 A은 이미지 입력을 지원하지 않아요."),
  ).toBeDefined();
  expect(screen.queryByRole("dialog")).toBeNull();
  expect(onRun).not.toHaveBeenCalled();
});

test("확인창을 연 뒤 모델이 비활성화되면 호출하지 않는다", async () => {
  const onRun = vi.fn();
  const page = render(<SimulatorPage choices={choices} onRun={onRun} />);
  fill();
  fireEvent.click(screen.getByRole("button", { name: "비교 실행" }));
  const dialog = await screen.findByRole("dialog", {
    name: "비교를 실행할까요?",
  });
  page.rerender(
    <SimulatorPage
      choices={choices.map((item) => ({ ...item, selectable: false }))}
      onRun={onRun}
    />,
  );
  fireEvent.click(within(dialog).getByRole("button", { name: "실행하기" }));
  expect(
    await screen.findByText(
      "고를 수 없는 모델이 있어요. 모델을 다시 골라 주세요.",
    ),
  ).toBeDefined();
  expect(onRun).not.toHaveBeenCalled();
});

test("실행 요청 실패에서 내부 오류를 노출하거나 성공 결과를 만들지 않는다", async () => {
  const onRun = vi.fn(() => Promise.reject(new Error("internal-secret")));
  render(<SimulatorPage choices={choices} onRun={onRun} />);
  fill();
  fireEvent.click(screen.getByRole("button", { name: "비교 실행" }));
  const dialog = await screen.findByRole("dialog", {
    name: "비교를 실행할까요?",
  });
  fireEvent.click(within(dialog).getByRole("button", { name: "실행하기" }));
  expect(
    await screen.findByText(
      "실행 요청을 보내지 못했어요. 잠시 후 다시 시도해 주세요.",
    ),
  ).toBeDefined();
  expect(screen.queryByText("internal-secret")).toBeNull();
  expect(screen.getByText("아직 실행 결과가 없어요")).toBeDefined();
});

test("이미지 형식 오류를 선택 즉시 알리고 목록에 추가하지 않는다", async () => {
  render(<SimulatorPage />);
  const chooser = imageInput();
  fireEvent.change(chooser, {
    target: {
      files: [new File(["svg"], "invalid.svg", { type: "image/svg+xml" })],
    },
  });
  expect(await screen.findByRole("alert")).toHaveProperty(
    "textContent",
    "JPG·PNG·WebP 파일을 골라 주세요.",
  );
  expect(screen.queryByText("invalid.svg")).toBeNull();
  expect(chooser.getAttribute("aria-invalid")).toBe("true");
});

test.each([
  IMAGE_LIMITS.maxBytes - 1,
  IMAGE_LIMITS.maxBytes,
  IMAGE_LIMITS.maxBytes + 1,
])("이미지 %i bytes를 선택 시 검증한다", async (size) => {
  render(<SimulatorPage />);
  fireEvent.change(imageInput(), {
    target: {
      files: [
        new File([new Uint8Array(size)], "boundary.png", { type: "image/png" }),
      ],
    },
  });
  if (size > IMAGE_LIMITS.maxBytes) {
    expect(await screen.findByRole("alert")).toBeDefined();
    expect(screen.queryByText("boundary.png")).toBeNull();
  } else {
    expect(await screen.findByText("boundary.png")).toBeDefined();
    expect(screen.queryByRole("alert")).toBeNull();
  }
});

test("이미지 개수 초과 시 기존 선택을 보존하고 제거·재선택으로 오류를 해소한다", async () => {
  render(<SimulatorPage />);
  const chooser = imageInput();
  const png = (name: string) =>
    new File(["image"], name, { type: "image/png" });
  fireEvent.change(chooser, {
    target: { files: [png("first.png"), png("second.png")] },
  });
  fireEvent.change(chooser, {
    target: { files: [png("third.png"), png("fourth.png"), png("fifth.png")] },
  });
  expect(
    await screen.findByText("이미지는 최대 4개까지 고를 수 있어요."),
  ).toBeDefined();
  expect(screen.getByText("first.png")).toBeDefined();
  expect(screen.getByText("second.png")).toBeDefined();
  expect(screen.queryByText("third.png")).toBeNull();
  fireEvent.click(screen.getByRole("button", { name: "second.png 제거" }));
  expect(screen.queryByRole("alert")).toBeNull();
  fireEvent.change(chooser, {
    target: { files: [png("third.png"), png("fourth.png"), png("fifth.png")] },
  });
  expect(await screen.findByText("fifth.png")).toBeDefined();
  expect(screen.getAllByRole("button", { name: /\.png 제거$/ })).toHaveLength(
    4,
  );
});

test.each(["prompt", "text"] as const)(
  "%s 초과 입력을 자르지 않고 실행을 차단한다",
  async (field) => {
    const onRun = vi.fn();
    render(<SimulatorPage choices={choices} onRun={onRun} />);
    fill();
    if (field === "text") openExtra("입력 텍스트");
    const input = screen.getByLabelText(
      field === "prompt" ? "Prompt" : "입력 텍스트",
    );
    const value = "가".repeat(TEXT_LIMIT + 1);
    fireEvent.change(input, { target: { value } });
    expect((input as HTMLTextAreaElement).value).toBe(value);
    expect(screen.queryByRole("alert")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "비교 실행" }));
    expect(
      await screen.findByText("2,000자 이내로 입력해 주세요."),
    ).toBeDefined();
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(onRun).not.toHaveBeenCalled();
  },
);

test("모델이 모자라면 실행 버튼 옆에 몇 개 더 골라야 하는지 적는다", () => {
  render(<SimulatorPage choices={choices} onRun={vi.fn()} />);
  expect(
    screen.getByText("모델을 2개 더 고르면 실행할 수 있어요"),
  ).toBeDefined();
  fireEvent.click(screen.getByRole("button", { name: "모델 검색" }));
  fireEvent.click(
    screen.getByRole("checkbox", { name: "모델 A · Provider 1" }),
  );
  fireEvent.click(screen.getByRole("button", { name: "선택 적용" }));
  expect(
    screen.getByText("모델을 1개 더 고르면 실행할 수 있어요"),
  ).toBeDefined();
  fireEvent.click(screen.getByRole("button", { name: "모델 검색" }));
  fireEvent.click(
    screen.getByRole("checkbox", { name: "모델 A · Provider 2" }),
  );
  fireEvent.click(screen.getByRole("button", { name: "선택 적용" }));
  expect(screen.queryByText(/더 고르면 실행할 수 있어요/)).toBeNull();
});

test("이 화면에서 실행하면 폼이 실행 조건 요약으로 접히고 다시 펼칠 수 있다", async () => {
  const onRun = vi.fn(() => Promise.resolve());
  const page = render(<SimulatorPage choices={choices} onRun={onRun} />);
  fill();
  fireEvent.click(screen.getByRole("button", { name: "비교 실행" }));
  const dialog = await screen.findByRole("dialog", {
    name: "비교를 실행할까요?",
  });
  fireEvent.click(within(dialog).getByRole("button", { name: "실행하기" }));
  await waitFor(() => expect(onRun).toHaveBeenCalledTimes(1));
  page.rerender(
    <SimulatorPage
      choices={choices}
      onRun={onRun}
      view={{ kind: "ready", run: dbMock.runs[0] }}
    />,
  );
  const summary = screen.getByRole("region", { name: "실행 조건" });
  expect(within(summary).getByText(/요약해 주세요\./)).toBeDefined();
  expect(screen.queryByLabelText("Prompt")).toBeNull();
  fireEvent.click(screen.getByRole("button", { name: "조건 수정해 새 비교" }));
  expect((screen.getByLabelText("Prompt") as HTMLTextAreaElement).value).toBe(
    "요약해 주세요.",
  );
});

test("주소로 결과만 열었을 때는 빈 폼을 접지 않는다", () => {
  render(
    <SimulatorPage
      choices={choices}
      onRun={vi.fn()}
      view={{ kind: "ready", run: dbMock.runs[0] }}
    />,
  );
  expect(screen.getByLabelText("Prompt")).toBeDefined();
  expect(screen.queryByRole("region", { name: "실행 조건" })).toBeNull();
});
