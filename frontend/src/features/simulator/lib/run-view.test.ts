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
  ["0.1", "0.2", "0.3"],
])(
  "확정 %s·추정 %s이면 서버 합계 %s를 그대로 쓴다",
  (confirmed, estimated, total) => {
    expect(
      toRunView({
        ...RUN_DETAIL,
        summary: {
          ...summary,
          confirmed_cost_usd: confirmed,
          estimated_cost_usd: estimated,
          total_cost_usd: total,
        },
      }).totalCost,
    ).toBe(total);
  },
);

test("합계는 화면에서 다시 더하지 않고 서버 값을 쓴다", () => {
  expect(
    toRunView({
      ...RUN_DETAIL,
      summary: {
        ...summary,
        confirmed_cost_usd: "0.1",
        estimated_cost_usd: "0.2",
        total_cost_usd: "0.300000000000",
      },
    }).totalCost,
  ).toBe("0.300000000000");
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

test.each([
  ["ACTIVE", "활성"],
  ["INACTIVE", "비활성"],
  ["TESTING", "검증 중"],
] as const)("실행 당시 모델 상태 %s를 %s로 옮긴다", (status, label) => {
  const [first, second] = RUN_DETAIL.results;
  expect(
    toRunView({
      ...RUN_DETAIL,
      results: [{ ...first, model_status_at_run: status }, second],
    }).slots[0].statusAtRun,
  ).toBe(label);
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
