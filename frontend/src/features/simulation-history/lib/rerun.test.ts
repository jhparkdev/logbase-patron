import { expect, test } from "vitest";
import type { HistoryDetailView } from "./presentation";
import { rerunBlockReason } from "./rerun";

const detail: HistoryDetailView = {
  key: "run",
  input: {
    kind: "available",
    prompt: "원문",
    text: "입력",
    schema: "",
    attachments: [],
  },
  settings: [],
  models: [
    { key: "a", name: "기존 모델", provider: "p", currentState: "inactive" },
  ],
};
test("비활성 모델의 과거 결과는 유지하며 P-04에서 교체할 수 있다", () => {
  expect(rerunBlockReason(detail)).toBeUndefined();
});
test("누락된 입력과 접근할 수 없는 이미지는 사유를 안내하고 재실행을 막는다", () => {
  expect(rerunBlockReason({ ...detail, input: { kind: "missing" } })).toContain(
    "입력",
  );
  expect(
    rerunBlockReason({
      ...detail,
      input: {
        kind: "available",
        prompt: " ",
        text: "",
        schema: "",
        attachments: [],
      },
    }),
  ).toContain("Prompt");
  expect(
    rerunBlockReason({
      ...detail,
      input: {
        kind: "available",
        prompt: "원문",
        text: "",
        schema: "",
        attachments: [{ key: "i", name: "image.png", available: false }],
      },
    }),
  ).toContain("이미지");
});
test("현재 모델 정보를 확인하기 전에는 재실행 가능하다고 표시하지 않는다", () => {
  expect(
    rerunBlockReason({
      ...detail,
      models: [{ ...detail.models[0], currentState: "unknown" }],
    }),
  ).toContain("현재 모델");
});
