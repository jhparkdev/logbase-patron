import { expect, test } from "vitest";
import { historySelectOptions } from "./filter-options";

const MODELS = [{ key: "7", name: "모델 A" }];

test("전체 항목을 맨 앞에 두고 선택지를 이어 붙인다", () => {
  expect(historySelectOptions("모델", MODELS, "")).toEqual([
    { value: "", label: "전체" },
    { value: "7", label: "모델 A" },
  ]);
});

test("주소의 값이 선택지에 없으면 지울 수 있게 선택한 항목을 남긴다", () => {
  expect(historySelectOptions("모델", MODELS, "9")).toEqual([
    { value: "", label: "전체" },
    { value: "9", label: "선택한 모델" },
    { value: "7", label: "모델 A" },
  ]);
});

test("전체 값을 따로 정하면 그 값을 전체 항목으로 쓴다", () => {
  expect(historySelectOptions("실행 상태", [], "all", "all")).toEqual([
    { value: "all", label: "전체" },
  ]);
});
