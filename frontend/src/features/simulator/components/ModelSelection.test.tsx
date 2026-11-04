// @vitest-environment jsdom
import {
  cleanup,
  fireEvent,
  render,
  screen,
  within,
} from "@testing-library/react";
import { FormProvider, useForm } from "react-hook-form";
import { afterEach, beforeAll, expect, test } from "vitest";
import { createComparisons } from "../lib/comparisons";
import { createDefaultValues, type SimulatorFormValues } from "../lib/form";
import type { ModelChoice } from "../lib/presentation";
import { ModelSelection } from "./ModelSelection";

const choices: ModelChoice[] = Array.from({ length: 6 }, (_, index) => ({
  key: `model-${index}:provider`,
  name: index < 2 ? "같은 모델" : `모델 ${index}`,
  provider: `Provider ${index}`,
  selectable: index !== 5,
  unavailableReason: index === 5 ? "비활성 모델" : undefined,
  supportsImages: index % 2 === 0,
  supportedParameters: [],
}));

function Form({
  selections = [],
  catalog = choices,
  unavailable = false,
}: {
  selections?: string[];
  catalog?: ModelChoice[];
  unavailable?: boolean;
}) {
  const form = useForm<SimulatorFormValues>({
    defaultValues: createDefaultValues({
      comparisons: createComparisons(selections),
    }),
  });
  return (
    <FormProvider {...form}>
      <form>
        <ModelSelection choices={catalog} unavailable={unavailable} />
      </form>
    </FormProvider>
  );
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

function openPicker() {
  fireEvent.click(screen.getByRole("button", { name: "모델 검색" }));
  return screen.getByRole("dialog", { name: "비교 모델 선택" });
}
function select(index: number) {
  fireEvent.click(
    screen.getByRole("checkbox", {
      name: `${choices[index].name} · ${choices[index].provider}`,
    }),
  );
}

test("한 모달에서 여러 Provider를 선택하고 적용할 때만 비교 모델에 반영한다", () => {
  render(<Form />);
  const dialog = openPicker();
  expect(
    within(dialog)
      .getByRole("button", { name: "선택 적용" })
      .hasAttribute("disabled"),
  ).toBe(true);
  select(0);
  expect(
    within(dialog)
      .getByRole("button", { name: "선택 적용" })
      .hasAttribute("disabled"),
  ).toBe(false);
  select(1);
  expect(screen.queryByRole("list", { name: "선택한 비교 모델" })).toBeNull();
  fireEvent.click(within(dialog).getByRole("button", { name: "선택 적용" }));
  expect(screen.queryByRole("dialog")).toBeNull();
  const selected = screen.getByRole("list", { name: "선택한 비교 모델" });
  expect(within(selected).getAllByRole("listitem")).toHaveLength(2);
  expect(within(selected).getByText("Provider 0")).toBeDefined();
  expect(within(selected).getByText("Provider 1")).toBeDefined();
  expect(document.activeElement).toBe(
    screen.getByRole("button", { name: "모델 검색" }),
  );
});

test.each(["닫기", "Escape"])(
  "%s는 임시 변경을 버리고 다시 열면 적용된 선택에서 시작한다",
  (method) => {
    render(<Form selections={[choices[0].key, choices[1].key]} />);
    const dialog = openPicker();
    select(0);
    select(2);
    if (method === "닫기")
      fireEvent.click(within(dialog).getByRole("button", { name: "닫기" }));
    else
      fireEvent(
        dialog,
        new Event("cancel", { bubbles: true, cancelable: true }),
      );
    const selected = screen.getByRole("list", { name: "선택한 비교 모델" });
    expect(within(selected).getByText("Provider 0")).toBeDefined();
    expect(within(selected).queryByText("Provider 2")).toBeNull();
    openPicker();
    expect(
      (
        screen.getByRole("checkbox", {
          name: "같은 모델 · Provider 0",
        }) as HTMLInputElement
      ).checked,
    ).toBe(true);
    expect(
      (
        screen.getByRole("checkbox", {
          name: "모델 2 · Provider 2",
        }) as HTMLInputElement
      ).checked,
    ).toBe(false);
  },
);

test("모델명과 Provider를 검색하고 검색 밖의 선택을 유지한다", async () => {
  render(<Form />);
  const dialog = openPicker();
  select(0);
  const input = within(dialog).getByRole("searchbox", { name: "모델 검색어" });
  expect((input as HTMLInputElement).form).toBeNull();
  fireEvent.change(input, { target: { value: "  모델 2 PROVIDER 2  " } });
  const result = await within(dialog).findByRole("checkbox", {
    name: "모델 2 · Provider 2",
  });
  // 검색 반영을 기다린 뒤 표시된 결과가 하나인지 확인한다.
  await screen.findByText("검색 결과 1개");
  expect(within(dialog).getAllByRole("checkbox")).toHaveLength(1);
  fireEvent.click(result);
  fireEvent.change(input, { target: { value: "찾을 수 없는 검색어" } });
  expect(await within(dialog).findByText("검색 결과가 없어요")).toBeDefined();
  fireEvent.click(within(dialog).getByRole("button", { name: "선택 적용" }));
  expect(
    within(screen.getByRole("list", { name: "선택한 비교 모델" })).getAllByRole(
      "listitem",
    ),
  ).toHaveLength(2);
});

test("최대 네 개를 선택해도 해제와 교체가 가능하고 비활성 모델은 선택하지 못한다", () => {
  render(<Form />);
  const dialog = openPicker();
  expect(
    screen
      .getByRole("checkbox", { name: "모델 5 · Provider 5" })
      .hasAttribute("disabled"),
  ).toBe(true);
  for (const index of [0, 1, 2, 3]) select(index);
  expect(
    screen
      .getByRole("checkbox", { name: "모델 4 · Provider 4" })
      .hasAttribute("disabled"),
  ).toBe(true);
  select(0);
  select(4);
  fireEvent.click(within(dialog).getByRole("button", { name: "선택 적용" }));
  openPicker();
  expect(
    screen
      .getAllByRole("checkbox")
      .filter((input) => (input as HTMLInputElement).checked),
  ).toHaveLength(4);
});

test("목록이 갱신되어 선택 모델이 비활성화되면 적용을 막고 해제할 수 있다", () => {
  const page = render(<Form selections={[choices[0].key, choices[1].key]} />);
  const dialog = openPicker();
  page.rerender(
    <Form
      catalog={choices.map((item, index) =>
        index === 0 ? { ...item, selectable: false } : item,
      )}
    />,
  );
  expect(
    within(dialog)
      .getByRole("button", { name: "선택 적용" })
      .hasAttribute("disabled"),
  ).toBe(true);
  expect(
    screen
      .getByRole("checkbox", { name: "같은 모델 · Provider 0" })
      .hasAttribute("disabled"),
  ).toBe(false);
  select(0);
  select(2);
  expect(
    within(dialog)
      .getByRole("button", { name: "선택 적용" })
      .hasAttribute("disabled"),
  ).toBe(false);
});

test("카탈로그 준비 전에는 검색을 막고 유실된 복원 모델은 제거할 수 있다", () => {
  const page = render(<Form unavailable />);
  expect(
    screen.getByRole("button", { name: "모델 검색" }).hasAttribute("disabled"),
  ).toBe(true);
  page.unmount();
  render(<Form selections={["missing:model", choices[0].key]} />);
  const dialog = openPicker();
  expect(
    within(dialog)
      .getByRole("button", { name: "선택 적용" })
      .hasAttribute("disabled"),
  ).toBe(true);
  fireEvent.click(
    within(dialog).getByRole("button", { name: "목록에 없는 모델 선택 해제" }),
  );
  select(1);
  fireEvent.click(within(dialog).getByRole("button", { name: "선택 적용" }));
  expect(screen.queryByRole("dialog")).toBeNull();
});

test("가장 싼 업체에는 실제 업체 이름 옆에 최저가 배지를 붙인다", () => {
  const catalog: ModelChoice[] = [
    { ...choices[0], provider: "DeepInfra", cheapest: true },
    { ...choices[1], key: "model-0:other", provider: "Io Net" },
  ];
  render(<Form catalog={catalog} />);
  const dialog = openPicker();
  const cheapestRow = within(dialog)
    .getByRole("checkbox", { name: "같은 모델 · DeepInfra" })
    .closest("tr");
  const otherRow = within(dialog)
    .getByRole("checkbox", { name: "같은 모델 · Io Net" })
    .closest("tr");
  expect(
    within(cheapestRow as HTMLElement).getByText("DeepInfra"),
  ).toBeDefined();
  expect(within(cheapestRow as HTMLElement).getByText("최저가")).toBeDefined();
  expect(within(otherRow as HTMLElement).queryByText("최저가")).toBeNull();
});

function ImageOutputForm({ selections }: { selections: string[] }) {
  const form = useForm<SimulatorFormValues>({
    defaultValues: createDefaultValues({
      outputType: "IMAGE",
      comparisons: createComparisons(selections),
    }),
  });
  return (
    <FormProvider {...form}>
      <form>
        <ModelSelection
          choices={choices.map((item, index) => ({
            ...item,
            generatesImages: index === 1,
          }))}
          unavailable={false}
          settings={<p>공통 설정 영역</p>}
        />
      </form>
    </FormProvider>
  );
}

test("이미지 출력이면 보내지 않는 공통 설정·모델별 설정·복제를 숨긴다", () => {
  render(<ImageOutputForm selections={[choices[1].key]} />);
  const [card] = screen.getAllByRole("listitem");
  expect(screen.queryByText("공통 설정 영역")).toBeNull();
  expect(screen.queryByText(/모델 카드의 설정이 실제로 전송돼요/)).toBeNull();
  expect(within(card).queryByText("Temperature")).toBeNull();
  expect(within(card).queryByText("모델별 설정")).toBeNull();
  expect(within(card).queryByText("공통")).toBeNull();
  expect(
    within(card).queryByRole("button", { name: /다른 설정으로 비교/ }),
  ).toBeNull();
  expect(within(card).queryByText("JSON")).toBeNull();
  expect(within(card).getByText("이미지")).toBeDefined();
  expect(within(card).getByText("단가 USD/1M")).toBeDefined();
  expect(within(card).getByRole("button", { name: /제거/ })).toBeDefined();
});

test("이미지 출력이면 이미지를 만드는 모델만 고르게 하고 이미 고른 다른 모델 카드에 경고한다", () => {
  render(<ImageOutputForm selections={[choices[2].key]} />);
  expect(
    screen.getByText(
      "이미지를 만들지 못해요. 출력 형식을 텍스트로 바꾸거나 모델을 바꿔 주세요.",
    ),
  ).toBeDefined();
  const dialog = openPicker();
  expect(within(dialog).queryByText("JSON")).toBeNull();
  const options = within(dialog).getAllByRole("checkbox");
  expect(options.map((option) => option.getAttribute("aria-label"))).toEqual([
    `${choices[1].name} · ${choices[1].provider}`,
  ]);
});
