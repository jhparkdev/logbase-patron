import { expect, test } from "vitest";
import {
  modalitiesFlow,
  modalitiesLabel,
  modalityLabel,
  providerOptions,
  STATUS_OPTIONS,
  statusBadge,
  statusChangeTargets,
  testCostView,
  testResultView,
  timeOrNone,
} from "./view";

test("모델 상태를 한국어 글자와 색으로 바꾼다", () => {
  expect(statusBadge("TESTING")).toEqual({ tone: "blue", label: "검증 중" });
  expect(statusBadge("ACTIVE")).toEqual({ tone: "green", label: "사용 중" });
  expect(statusBadge("INACTIVE")).toEqual({ tone: "grey", label: "사용 중단" });
});

test("연결 테스트 결과는 성공이 초록, 실패와 시간 초과가 빨강이다", () => {
  expect(testResultView("SUCCESS")).toEqual({ label: "성공", dot: "green" });
  expect(testResultView("FAILED")).toEqual({ label: "실패", dot: "red" });
  expect(testResultView("TIMEOUT")).toEqual({ label: "시간 초과", dot: "red" });
});

test("입력 형식을 한국어로 바꾸고, 모르는 형식은 그대로 보여 준다", () => {
  expect(modalityLabel("text")).toBe("텍스트");
  expect(modalityLabel("image")).toBe("이미지");
  expect(modalityLabel("hologram")).toBe("hologram");
});

test("상태 선택지는 전체와 세 상태를 한국어 글자로 보여 준다", () => {
  expect(STATUS_OPTIONS).toEqual([
    { value: "", label: "상태 전체" },
    { value: "TESTING", label: "검증 중" },
    { value: "ACTIVE", label: "사용 중" },
    { value: "INACTIVE", label: "사용 중단" },
  ]);
});

test("제공사 선택지는 전체 뒤에 받은 제공사를 모델 수와 함께 순서대로 둔다", () => {
  const providers = [
    { provider: "openai", model_count: 3 },
    { provider: "mistralai", model_count: 1 },
  ];
  expect(providerOptions(providers, undefined)).toEqual([
    { value: "", label: "Provider 전체" },
    { value: "openai", label: "openai (3)" },
    { value: "mistralai", label: "mistralai (1)" },
  ]);
});

test("고른 제공사가 받은 목록에 없으면 모델 수 없이 이름만 선택지에 남긴다", () => {
  expect(providerOptions([], "openai")).toEqual([
    { value: "", label: "Provider 전체" },
    { value: "openai", label: "openai" },
  ]);
  expect(
    providerOptions([{ provider: "openai", model_count: 3 }], "openai"),
  ).toHaveLength(2);
});

test("입력 형식 여러 개는 한국어 이름을 쉼표로 이어 보여 준다", () => {
  expect(modalitiesLabel(["text", "image"])).toBe("텍스트, 이미지");
  expect(modalitiesLabel(["text"])).toBe("텍스트");
});

test("테스트 비용은 확정과 추정을 구분하고 모르면 금액 없이 미확인이다", () => {
  expect(
    testCostView({ cost_usd: "0.0004", cost_status: "CONFIRMED" }),
  ).toEqual({ kind: "confirmed", amount: "0.0004" });
  expect(
    testCostView({ cost_usd: "0.0004", cost_status: "ESTIMATED" }),
  ).toEqual({ kind: "estimated", amount: "0.0004" });
  expect(testCostView({ cost_usd: null, cost_status: "UNKNOWN" })).toEqual({
    kind: "unknown",
    amount: null,
  });
});

test("비용 금액이 없으면 상태가 확정이어도 미확인으로 본다", () => {
  expect(testCostView({ cost_usd: null, cost_status: "CONFIRMED" })).toEqual({
    kind: "unknown",
    amount: null,
  });
});

test("상태 변경 버튼은 현재 상태를 뺀 사용 중·사용 중단이다", () => {
  expect(statusChangeTargets("TESTING")).toEqual(["ACTIVE", "INACTIVE"]);
  expect(statusChangeTargets("ACTIVE")).toEqual(["INACTIVE"]);
  expect(statusChangeTargets("INACTIVE")).toEqual(["ACTIVE"]);
});

test("시각이 없으면 빈칸 대신 없음, 있으면 KST로 보여 준다", () => {
  expect(timeOrNone(null)).toBe("없음");
  expect(timeOrNone("2026-10-31T05:32:21Z")).toBe("2026-10-31 14:32:21");
});

test("입력 형식 → 출력 형식으로 한 줄에 보여 준다", () => {
  expect(modalitiesFlow(["text", "image"], ["text"])).toBe(
    "텍스트·이미지 → 텍스트",
  );
  expect(modalitiesFlow(["text"], ["text", "image"])).toBe(
    "텍스트 → 텍스트·이미지",
  );
});
