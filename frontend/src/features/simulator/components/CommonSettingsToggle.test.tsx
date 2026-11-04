// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { FormProvider, useForm } from "react-hook-form";
import { afterEach, expect, test } from "vitest";
import { createComparison } from "../lib/comparisons";
import {
  createDefaultValues,
  type SimulatorDraft,
  type SimulatorFormValues,
} from "../lib/form";
import type { ModelChoice } from "../lib/presentation";
import { AdvancedSettings } from "./AdvancedSettings";
import { ComparisonSettings } from "./ComparisonSettings";

afterEach(cleanup);

const choice: ModelChoice = {
  key: "a:p",
  name: "모델 A",
  provider: "p",
  selectable: true,
  supportsImages: false,
  supportedParameters: ["temperature"],
  tuningParameters: [
    { key: "temperature", kind: "number", min: 0, max: 1, step: 0.1 },
  ],
};

function Settings() {
  const form = useForm<SimulatorFormValues, unknown, SimulatorDraft>({
    defaultValues: createDefaultValues({
      comparisons: [
        createComparison(choice.key, "first"),
        createComparison(choice.key, "second"),
      ],
    }),
  });
  return (
    <FormProvider {...form}>
      <AdvancedSettings open onToggle={() => undefined} choices={[choice]} />
      <ComparisonSettings index={0} choice={choice} />
    </FormProvider>
  );
}

const commonToggle = () =>
  screen.getByRole<HTMLInputElement>("checkbox", { name: "공통 설정 사용" });

test("공통 설정은 처음에 꺼져 있고 켤 수 있다", () => {
  render(<Settings />);
  expect(commonToggle().checked).toBe(false);
  expect(commonToggle().disabled).toBe(false);
  fireEvent.click(commonToggle());
  expect(commonToggle().checked).toBe(true);
});

test("모델별 설정을 켜면 공통 설정을 끄고 잠그며, 해제해도 꺼진 채로 둔다", () => {
  render(<Settings />);
  fireEvent.click(commonToggle());
  fireEvent.click(screen.getByRole("button", { name: "비교 항목 1 설정" }));
  const custom = screen.getByRole<HTMLInputElement>("checkbox", {
    name: "모델별 설정 사용",
  });
  fireEvent.click(custom);
  expect(commonToggle().checked).toBe(false);
  expect(commonToggle().disabled).toBe(true);
  fireEvent.click(custom);
  expect(commonToggle().disabled).toBe(false);
  expect(commonToggle().checked).toBe(false);
});
