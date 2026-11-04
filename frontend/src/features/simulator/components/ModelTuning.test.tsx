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
import type { TuningParameter } from "../lib/parameters";
import type { ModelChoice } from "../lib/presentation";
import { ModelPickerDialog } from "./ModelPickerDialog";
import { SimulatorPage } from "./SimulatorPage";

const choices: ModelChoice[] = ["a", "b", "c", "d"].map((name) => ({
  key: `${name}:p`,
  name: `모델 ${name.toUpperCase()}`,
  provider: "p",
  selectable: true,
  supportsImages: true,
  supportedParameters: ["temperature", "max_tokens", "reasoning"],
  tuningParameters: [
    { key: "temperature", kind: "number", min: 0, max: 1, step: 0.1 },
    { key: "maxTokens", kind: "number", min: 1, max: 1024, step: 1 },
    {
      key: "reasoningEffort",
      kind: "choice",
      options: [
        { value: "low", label: "낮음" },
        { value: "high", label: "높음" },
      ],
    },
  ],
}));
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
function show(catalog = choices) {
  const onRun = vi.fn<(draft: SimulatorDraft) => void>();
  const comparisons = createComparisons(["a:p", "b:p"]);
  render(
    <SimulatorPage
      choices={catalog}
      onRun={onRun}
      initialValues={{ prompt: "작업", temperature: "0.3", comparisons }}
    />,
  );
  return { onRun, comparisons };
}
function settings(index: number) {
  const button = screen.getByRole("button", {
    name: `비교 항목 ${index} 설정`,
  });
  if (button.getAttribute("aria-expanded") !== "true") fireEvent.click(button);
  return within(screen.getByRole("group", { name: `비교 항목 ${index} 설정` }));
}

test("개별 설정을 편집해도 다른 항목과 공통값을 바꾸지 않고 접었다 펼쳐도 유지한다", () => {
  show();
  const own = settings(1);
  fireEvent.click(own.getByLabelText("모델별 설정 사용"));
  fireEvent.change(own.getByLabelText("Temperature"), {
    target: { value: "0.7" },
  });
  fireEvent.click(screen.getByRole("button", { name: "비교 항목 1 설정" }));
  expect(
    (settings(1).getByLabelText("Temperature") as HTMLInputElement).value,
  ).toBe("0.7");
  fireEvent.click(own.getByLabelText("모델별 설정 사용"));
  fireEvent.click(own.getByLabelText("모델별 설정 사용"));
  expect((own.getByLabelText("Temperature") as HTMLInputElement).value).toBe(
    "0.7",
  );
  expect(
    (settings(2).getByLabelText("모델별 설정 사용") as HTMLInputElement)
      .checked,
  ).toBe(false);
  fireEvent.click(screen.getByRole("button", { name: /^공통 설정 선택사항$/ }));
  expect(
    (screen.getByLabelText("공통 Temperature") as HTMLInputElement).value,
  ).toBe("0.3");
  fireEvent.click(own.getByRole("button", { name: "공통 설정으로" }));
  expect(
    (own.getByLabelText("모델별 설정 사용") as HTMLInputElement).checked,
  ).toBe(false);
});

test("같은 대상을 복제한 뒤 다른 설정으로 제출하고 항목 ID와 요청 설정을 구분한다", async () => {
  const { onRun, comparisons } = show();
  fireEvent.click(
    screen.getByRole("button", { name: "비교 모델 1 다른 설정으로 비교" }),
  );
  const own = settings(3);
  fireEvent.change(own.getByLabelText("Temperature"), {
    target: { value: "0.7" },
  });
  fireEvent.change(own.getByLabelText("추론 강도"), {
    target: { value: "high" },
  });
  fireEvent.click(screen.getByRole("button", { name: "비교 실행" }));
  const dialog = await screen.findByRole("dialog", {
    name: "비교를 실행합니다",
  });
  expect(within(dialog).getByText(/Temperature: 0.7/)).toBeDefined();
  fireEvent.click(within(dialog).getByRole("button", { name: "실행하기" }));
  await waitFor(() => expect(onRun).toHaveBeenCalledOnce());
  const submitted = onRun.mock.calls[0][0].comparisons;
  expect(submitted[0].comparisonId).toBe(comparisons[0].comparisonId);
  expect(submitted[2].comparisonId).not.toBe(comparisons[0].comparisonId);
  expect(submitted[2]).toMatchObject({
    modelKey: "a:p",
    settings: { temperature: 0.7, reasoningEffort: "high" },
  });
});

test("공통 설정을 켠 채 복제하면 복제 칸이 모델별 설정이라 공통 설정을 끄고 잠근다", () => {
  show();
  fireEvent.click(screen.getByRole("button", { name: /^공통 설정 선택사항$/ }));
  const common = screen.getByLabelText("공통 설정 사용") as HTMLInputElement;
  fireEvent.click(common);
  expect(common.checked).toBe(true);
  fireEvent.click(
    screen.getByRole("button", { name: "비교 모델 1 다른 설정으로 비교" }),
  );
  expect(common.checked).toBe(false);
  expect(common.disabled).toBe(true);
});

test("설정을 바꾸지 않은 복제 항목은 확인창에 진행하지 않고 숫자 표기만 다른 중복도 막는다", async () => {
  const { onRun } = show();
  // 모델별 설정을 쓰면 공통 설정은 꺼지므로, 원본 칸에 직접 넣은 값과 복제 칸의 값을 비교한다.
  const own = settings(1);
  fireEvent.click(own.getByLabelText("모델별 설정 사용"));
  fireEvent.change(own.getByLabelText("Temperature"), {
    target: { value: "0.3" },
  });
  fireEvent.click(
    screen.getByRole("button", { name: "비교 모델 1 다른 설정으로 비교" }),
  );
  fireEvent.change(settings(3).getByLabelText("Temperature"), {
    target: { value: "0.30" },
  });
  fireEvent.click(screen.getByRole("button", { name: "비교 실행" }));
  expect(await screen.findByText(/동일한 요청 설정/)).toBeDefined();
  expect(screen.queryByRole("dialog")).toBeNull();
  expect(onRun).not.toHaveBeenCalled();
});

test("모델별 범위 오류를 제출 후 펼쳐 보여 주고 지원 정보가 없으면 편집을 막는다", async () => {
  const page = show();
  const own = settings(1);
  fireEvent.click(own.getByLabelText("모델별 설정 사용"));
  fireEvent.change(own.getByLabelText("Temperature"), {
    target: { value: "1.5" },
  });
  fireEvent.click(screen.getByRole("button", { name: "비교 항목 1 설정" }));
  fireEvent.click(screen.getByRole("button", { name: "비교 실행" }));
  expect(await screen.findByText(/Temperature 값은 0~1/)).toBeDefined();
  await waitFor(() =>
    expect(
      screen
        .getByRole("button", { name: "비교 항목 1 설정" })
        .getAttribute("aria-expanded"),
    ).toBe("true"),
  );
  expect(page.onRun).not.toHaveBeenCalled();
  cleanup();
  show(choices.map((choice) => ({ ...choice, tuningParameters: undefined })));
  expect(
    settings(1).getByLabelText("모델별 설정 사용").hasAttribute("disabled"),
  ).toBe(true);
});

test("앞 항목을 제거해도 남은 항목의 ID·설정을 유지하고 카탈로그 재적용도 보존한다", async () => {
  const { onRun, comparisons } = show();
  const own = settings(2);
  fireEvent.click(own.getByLabelText("모델별 설정 사용"));
  fireEvent.change(own.getByLabelText("Temperature"), {
    target: { value: "0.8" },
  });
  fireEvent.click(screen.getByRole("button", { name: "비교 모델 1 제거" }));
  fireEvent.click(screen.getByRole("button", { name: "모델 검색" }));
  fireEvent.click(screen.getByRole("checkbox", { name: "모델 C · p" }));
  fireEvent.click(screen.getByRole("button", { name: "선택 적용" }));
  expect(
    (settings(1).getByLabelText("Temperature") as HTMLInputElement).value,
  ).toBe("0.8");
  fireEvent.click(screen.getByRole("button", { name: "비교 실행" }));
  const dialog = await screen.findByRole("dialog", {
    name: "비교를 실행합니다",
  });
  fireEvent.click(within(dialog).getByRole("button", { name: "실행하기" }));
  await waitFor(() => expect(onRun).toHaveBeenCalledOnce());
  expect(onRun.mock.calls[0][0].comparisons[0].comparisonId).toBe(
    comparisons[1].comparisonId,
  );
});

test("카탈로그 선택 제한은 서로 다른 모델 수가 아닌 복제를 포함한 비교 항목 수다", () => {
  render(
    <ModelPickerDialog
      choices={choices}
      selections={["a:p", "b:p"]}
      counts={{ "a:p": 2, "b:p": 1 }}
      unavailable={false}
      onApply={vi.fn()}
      onClose={vi.fn()}
    />,
  );
  fireEvent.click(screen.getByRole("checkbox", { name: "모델 C · p" }));
  expect(screen.getByText("선택한 비교 항목 4/4개")).toBeDefined();
  expect(
    screen
      .getByRole("checkbox", { name: "모델 D · p" })
      .hasAttribute("disabled"),
  ).toBe(true);
});

test("확인창이 열린 뒤 지원 범위가 바뀌면 실행을 막고 다시 확인하도록 한다", async () => {
  const onRun = vi.fn();
  const page = render(
    <SimulatorPage
      choices={choices}
      onRun={onRun}
      initialValues={{
        prompt: "작업",
        commonEnabled: true,
        temperature: "0.3",
        comparisons: createComparisons(["a:p", "b:p"]),
      }}
    />,
  );
  fireEvent.click(screen.getByRole("button", { name: "비교 실행" }));
  const dialog = await screen.findByRole("dialog", {
    name: "비교를 실행합니다",
  });
  const updated = choices.map((choice) => ({
    ...choice,
    tuningParameters: choice.tuningParameters?.map((parameter) =>
      parameter.key === "temperature" ? { ...parameter, max: 0.1 } : parameter,
    ),
  }));
  page.rerender(<SimulatorPage choices={updated} onRun={onRun} />);
  fireEvent.click(within(dialog).getByRole("button", { name: "실행하기" }));
  await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
  expect(screen.getAllByText(/Temperature 값은 0~0.1/).length).toBeGreaterThan(
    0,
  );
  expect(onRun).not.toHaveBeenCalled();
});

test("한 모델을 먼저 고른 뒤 복제해 같은 대상의 설정 비교를 시작할 수 있다", async () => {
  const onRun = vi.fn();
  render(
    <SimulatorPage
      choices={choices}
      onRun={onRun}
      initialValues={{ prompt: "작업" }}
    />,
  );
  fireEvent.click(screen.getByRole("button", { name: "모델 검색" }));
  fireEvent.click(screen.getByRole("checkbox", { name: "모델 A · p" }));
  fireEvent.click(screen.getByRole("button", { name: "선택 적용" }));
  expect(screen.queryByRole("dialog")).toBeNull();
  expect(
    screen.getByRole("button", { name: "비교 실행" }).hasAttribute("disabled"),
  ).toBe(true);
  fireEvent.click(
    screen.getByRole("button", { name: "비교 모델 1 다른 설정으로 비교" }),
  );
  fireEvent.change(settings(2).getByLabelText("Temperature"), {
    target: { value: "0" },
  });
  fireEvent.click(screen.getByRole("button", { name: "비교 실행" }));
  const dialog = await screen.findByRole("dialog", {
    name: "비교를 실행합니다",
  });
  expect(within(dialog).getByText("요청 설정: Temperature: 0")).toBeDefined();
});

test("공통 effort는 접었다 펴도 보존하고, 모델별 설정을 켜면 공통값 없이 개별값만 확인·제출한다", async () => {
  const { onRun } = show();
  const toggle = screen.getByRole("button", { name: /^공통 설정 선택사항$/ });
  fireEvent.click(toggle);
  fireEvent.click(screen.getByLabelText("공통 설정 사용"));
  fireEvent.change(screen.getByLabelText("공통 추론 강도 (effort)"), {
    target: { value: "high" },
  });
  fireEvent.click(toggle);
  fireEvent.click(toggle);
  expect(
    (screen.getByLabelText("공통 추론 강도 (effort)") as HTMLSelectElement)
      .value,
  ).toBe("high");
  const own = settings(2);
  fireEvent.click(own.getByLabelText("모델별 설정 사용"));
  fireEvent.change(own.getByLabelText("추론 강도"), {
    target: { value: "low" },
  });
  fireEvent.click(screen.getByRole("button", { name: "비교 실행" }));
  const dialog = await screen.findByRole("dialog", {
    name: "비교를 실행합니다",
  });
  // 모델별 설정을 켜는 순간 공통 설정이 꺼지므로 공통 effort(high)는 어느 칸에도 가지 않는다.
  expect(within(dialog).queryByText(/추론 강도: high/)).toBeNull();
  expect(within(dialog).getByText(/추론 강도: low/)).toBeDefined();
  fireEvent.click(within(dialog).getByRole("button", { name: "실행하기" }));
  await waitFor(() => expect(onRun).toHaveBeenCalledOnce());
  expect(onRun.mock.calls[0][0]).toMatchObject({
    commonEnabled: false,
    comparisons: [
      { settings: { mode: "shared" } },
      { settings: { reasoningEffort: "low" } },
    ],
  });
  // 다시 켤 때를 위해 공통 입력칸 값은 남는다
  expect(
    (screen.getByLabelText("공통 추론 강도 (effort)") as HTMLSelectElement)
      .value,
  ).toBe("high");
});

// 물려받은 effort를 받지 못하는 모델은 서버처럼 그 칸에서만 빼고 실행한다(temperature와 같은 규칙).
// 선택지를 화면이 모르는(unknown) 모델은 서버가 판단하도록 값을 그대로 둔다.
test.each(["unsupported", "unknown", "low-only"])(
  "공통 effort와 %s 모델이 함께 있으면 막지 않고 실행한다",
  async (kind) => {
    const catalog = choices.map((choice, index) =>
      index !== 1
        ? choice
        : {
            ...choice,
            supportedParameters:
              kind === "unsupported"
                ? ["temperature", "max_tokens"]
                : choice.supportedParameters,
            tuningParameters: choice.tuningParameters?.flatMap<TuningParameter>(
              (parameter) =>
                parameter.key !== "reasoningEffort"
                  ? [parameter]
                  : kind === "low-only"
                    ? [
                        {
                          ...parameter,
                          options: [{ value: "low", label: "낮음" }],
                        },
                      ]
                    : [],
            ),
          },
    );
    const { onRun } = show(catalog);
    fireEvent.click(
      screen.getByRole("button", { name: /^공통 설정 선택사항$/ }),
    );
    fireEvent.click(screen.getByLabelText("공통 설정 사용"));
    fireEvent.change(screen.getByLabelText("공통 추론 강도 (effort)"), {
      target: { value: "high" },
    });
    fireEvent.click(screen.getByRole("button", { name: "비교 실행" }));
    const dialog = await screen.findByRole("dialog", {
      name: "비교를 실행합니다",
    });
    expect(screen.queryByRole("alert")).toBeNull();
    const [first, second] = within(dialog).getAllByRole("listitem");
    expect(first.textContent).toContain("추론 강도: high");
    expect(second.textContent?.includes("추론 강도")).toBe(kind === "unknown");
    fireEvent.click(within(dialog).getByRole("button", { name: "실행하기" }));
    await waitFor(() => expect(onRun).toHaveBeenCalledOnce());
  },
);

test("공통값 초기화는 effort도 지우고 모델별 지정값은 유지한다", () => {
  show();
  fireEvent.click(screen.getByRole("button", { name: /^공통 설정 선택사항$/ }));
  fireEvent.change(screen.getByLabelText("공통 추론 강도 (effort)"), {
    target: { value: "high" },
  });
  const own = settings(1);
  fireEvent.click(own.getByLabelText("모델별 설정 사용"));
  fireEvent.change(own.getByLabelText("추론 강도"), {
    target: { value: "low" },
  });
  fireEvent.click(screen.getByRole("button", { name: "기본 설정으로" }));
  expect(
    (screen.getByLabelText("공통 추론 강도 (effort)") as HTMLSelectElement)
      .value,
  ).toBe("");
  expect((own.getByLabelText("추론 강도") as HTMLSelectElement).value).toBe(
    "low",
  );
});

test("확인 중 effort 선택지 정보가 사라져도 공통 effort는 서버 판단에 맡기고 실행한다", async () => {
  const onRun = vi.fn();
  const page = render(
    <SimulatorPage
      choices={choices}
      onRun={onRun}
      initialValues={{
        prompt: "작업",
        commonEnabled: true,
        reasoningEffort: "high",
        comparisons: createComparisons(["a:p", "b:p"]),
      }}
    />,
  );
  fireEvent.click(screen.getByRole("button", { name: "비교 실행" }));
  const dialog = await screen.findByRole("dialog", {
    name: "비교를 실행합니다",
  });
  page.rerender(
    <SimulatorPage
      choices={choices.map((choice) => ({ ...choice, tuningParameters: [] }))}
      onRun={onRun}
    />,
  );
  fireEvent.click(within(dialog).getByRole("button", { name: "실행하기" }));
  await waitFor(() => expect(onRun).toHaveBeenCalledOnce());
  expect(onRun.mock.calls[0][0]).toMatchObject({
    commonEnabled: true,
    reasoningEffort: "high",
  });
});
