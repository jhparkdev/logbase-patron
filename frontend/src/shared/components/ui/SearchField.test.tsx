// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, expect, test, vi } from "vitest";
import { SEARCH_DELAY_MS, SearchField } from "./SearchField";

beforeEach(() => vi.useFakeTimers());
afterEach(() => {
  cleanup();
  vi.useRealTimers();
});

function renderField(value?: string) {
  const onSearch = vi.fn();
  const field = (current?: string) => (
    <SearchField
      label="모델 검색"
      placeholder="검색"
      value={current}
      onSearch={onSearch}
    />
  );
  const { rerender } = render(field(value));
  return {
    onSearch,
    input: screen.getByRole<HTMLInputElement>("searchbox", {
      name: "모델 검색",
    }),
    changeValue: (next?: string) => rerender(field(next)),
  };
}

test("입력이 멈추기 전에는 검색하지 않는다", () => {
  const { onSearch, input } = renderField();

  fireEvent.change(input, { target: { value: "gpt" } });
  vi.advanceTimersByTime(SEARCH_DELAY_MS - 1);

  expect(onSearch).not.toHaveBeenCalled();
});

test("입력이 멈추면 마지막 값으로 한 번만 검색하고 앞뒤 공백은 뺀다", () => {
  const { onSearch, input } = renderField();

  fireEvent.change(input, { target: { value: "g" } });
  vi.advanceTimersByTime(SEARCH_DELAY_MS - 1);
  fireEvent.change(input, { target: { value: " gpt-4o " } });
  vi.advanceTimersByTime(SEARCH_DELAY_MS);

  expect(onSearch).toHaveBeenCalledTimes(1);
  expect(onSearch).toHaveBeenCalledWith("gpt-4o");
});

test("뒤로 가기처럼 바깥에서 검색어가 바뀌면 입력창도 따라 바뀐다", () => {
  const { input, changeValue } = renderField("gpt");
  expect(input.value).toBe("gpt");

  changeValue(undefined);

  expect(input.value).toBe("");
});

test("입력한 글자로 검색어가 바뀔 때는 입력창의 공백을 지우지 않는다", () => {
  const { input, changeValue } = renderField();

  fireEvent.change(input, { target: { value: "gpt " } });
  changeValue("gpt");

  expect(input.value).toBe("gpt ");
});
