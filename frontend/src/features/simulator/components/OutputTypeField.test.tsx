// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { FormProvider, useForm } from "react-hook-form";
import { afterEach, expect, test } from "vitest";
import { createDefaultValues, type SimulatorFormValues } from "../lib/form";
import { OutputTypeField } from "./OutputTypeField";

afterEach(cleanup);

function Form() {
  const form = useForm<SimulatorFormValues>({
    defaultValues: createDefaultValues(),
  });
  return (
    <FormProvider {...form}>
      <form>
        <OutputTypeField />
      </form>
    </FormProvider>
  );
}

test("처음에는 텍스트 출력이고 이미지 옵션을 보여 주지 않는다", () => {
  render(<Form />);
  expect(
    (screen.getByRole("radio", { name: "텍스트" }) as HTMLInputElement).checked,
  ).toBe(true);
  expect(screen.queryByLabelText("이미지 수")).toBeNull();
});

test("이미지 출력을 고르면 장 수·품질과 적용되지 않는 설정 안내를 보여 준다", () => {
  render(<Form />);
  fireEvent.click(screen.getByRole("radio", { name: "이미지" }));
  const count = screen.getByLabelText("이미지 수");
  expect(
    Array.from(count.querySelectorAll("option")).map(
      (item) => item.textContent,
    ),
  ).toEqual(["모델 기본값", "1장", "2장", "3장", "4장"]);
  const quality = screen.getByLabelText("품질");
  expect(
    Array.from(quality.querySelectorAll("option")).map(
      (item) => item.textContent,
    ),
  ).toEqual(["모델 기본값", "자동", "낮음", "보통", "높음"]);
  expect(
    screen.getByText(
      "이미지 생성에는 Temperature 같은 텍스트 설정과 JSON Schema를 보내지 않아요.",
    ),
  ).toBeDefined();
});
