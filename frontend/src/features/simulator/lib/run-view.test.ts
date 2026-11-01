import { expect, test } from "vitest";
import { RUN_DETAIL, RUN_ID } from "../../../test/simulationHistoryApi";
import { toRunView } from "./run-view";

const summary = RUN_DETAIL.summary;

test("실행 요약을 화면 값으로 바꾸고 전체 실행 시간을 계산한다", () => {
  expect(toRunView(RUN_DETAIL)).toMatchObject({
    key: RUN_ID,
    status: { label: "부분 성공", tone: "yellow", ongoing: false },
    requestedAt: summary.requested_at,
    durationMs: 5000,
    modelCount: 2,
    successCount: 1,
    failureCount: 1,
    confirmedCost: "0.125",
    estimatedCost: null,
    unknownCostCount: 1,
  });
});

test("끝나지 않은 실행은 시간을 비워 두고 진행 중으로 표시한다", () => {
  expect(
    toRunView({
      ...RUN_DETAIL,
      summary: { ...summary, status: "RUNNING", completed_at: null },
    }),
  ).toMatchObject({
    durationMs: null,
    status: { label: "진행 중", ongoing: true },
  });
});

test.each([
  ["0.1", null, "0.1"],
  [null, "0.2", "0.2"],
  [null, null, null],
  // 합산은 서버의 일이다. 서버가 합계를 주지 않으므로 둘 다 있으면 합계를 만들지 않는다
  ["0.1", "0.2", null],
])("확정 %s·추정 %s의 합계는 %s다", (confirmed, estimated, total) => {
  expect(
    toRunView({
      ...RUN_DETAIL,
      summary: {
        ...summary,
        confirmed_cost_usd: confirmed,
        estimated_cost_usd: estimated,
      },
    }).totalCost,
  ).toBe(total);
});

test("모델 칸의 성공 결과를 그대로 옮긴다", () => {
  expect(toRunView(RUN_DETAIL).slots[0]).toMatchObject({
    name: "Mistral Nemo",
    provider: "DeepInfra",
    actualModel: "mistralai/mistral-nemo",
    actualProvider: "DeepInfra",
    status: { label: "성공", tone: "green", ongoing: false },
    durationMs: 1500,
    inputTokens: 10,
    outputTokens: 20,
    cost: { kind: "confirmed", amount: "0.125" },
    jsonValidation: "성공",
    schemaValidation: "미적용",
    response: "모델 응답 원문",
  });
});

test("모델 칸마다 실제로 적용한 설정을 화면 이름으로 옮긴다", () => {
  const [first, second] = RUN_DETAIL.results;
  const { slots } = toRunView({
    ...RUN_DETAIL,
    results: [
      {
        ...first,
        execution_config: {
          reasoning_effort: "low",
          max_tokens: 512,
          temperature: 0,
        },
      },
      { ...second, execution_config: {} },
    ],
  });
  expect(slots[0].settings).toEqual([
    { label: "Temperature", value: "0" },
    { label: "최대 출력 토큰", value: "512" },
    { label: "추론 강도", value: "low" },
  ]);
  expect(slots[1].settings).toEqual([]);
});

test("과거 이력에 남은 다른 설정도 숨기지 않고 값이 없는 항목은 뺀다", () => {
  const [first, second] = RUN_DETAIL.results;
  const { slots } = toRunView({
    ...RUN_DETAIL,
    results: [
      {
        ...first,
        execution_config: { temperature: null, top_p: 0.5, stop: ["끝"] },
      },
      second,
    ],
  });
  expect(slots[0].settings).toEqual([
    { label: "top_p", value: "0.5" },
    { label: "stop", value: '["끝"]' },
  ]);
});

test("비용 미확인 칸은 0이 아니라 미확인으로 두고 실패 문구를 전달한다", () => {
  expect(toRunView(RUN_DETAIL).slots[1]).toMatchObject({
    status: { label: "시간 초과", tone: "yellow", ongoing: false },
    cost: { kind: "unknown", amount: null },
    jsonValidation: "미실행",
    schemaValidation: "미실행",
    response: null,
    errorMessage: "응답 시간을 초과했습니다.",
  });
});

test("추정 비용 칸은 추정으로 구분한다", () => {
  const [first, second] = RUN_DETAIL.results;
  expect(
    toRunView({
      ...RUN_DETAIL,
      results: [{ ...first, cost_status: "ESTIMATED" }, second],
    }).slots[0].cost,
  ).toEqual({ kind: "estimated", amount: "0.125" });
});

test("대기 중인 칸은 진행 중으로 본다", () => {
  const [first, second] = RUN_DETAIL.results;
  expect(
    toRunView({
      ...RUN_DETAIL,
      results: [{ ...first, status: "PENDING" }, second],
    }).slots[0].status,
  ).toEqual({ label: "대기", tone: "grey", ongoing: true });
});
