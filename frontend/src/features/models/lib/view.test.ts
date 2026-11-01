import { expect, test } from "vitest";
import { modalityLabel, statusBadge, testResultView } from "./view";

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
