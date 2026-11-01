import { expect, test } from "vitest";
import { ApiError } from "../../../shared/api/client";
import {
  HISTORY_ITEM,
  RERUN_DRAFT,
  RUN_DETAIL,
  RUN_ID,
} from "../../../test/simulationHistoryApi";
import {
  historyDetailState,
  isRunOngoing,
  toHistoryDetail,
  toHistoryRow,
} from "./view";

test("이력 한 행의 비용은 확정·추정을 더하지 않고 나눠 전달한다", () => {
  expect(
    toHistoryRow({
      ...HISTORY_ITEM,
      confirmed_cost_usd: "0.1",
      estimated_cost_usd: "0.2",
      unknown_cost_count: 0,
      cost_check_status: "추정 포함",
    }).cost,
  ).toEqual({
    confirmed: "0.1",
    estimated: "0.2",
    unknownCount: 0,
    checking: false,
  });
});

test("비용이 집계되지 않으면 금액을 0으로 만들지 않고 비워 둔다", () => {
  expect(
    toHistoryRow({
      ...HISTORY_ITEM,
      confirmed_cost_usd: null,
      estimated_cost_usd: null,
      unknown_cost_count: 2,
      cost_check_status: "확인 중",
    }).cost,
  ).toEqual({
    confirmed: null,
    estimated: null,
    unknownCount: 2,
    checking: true,
  });
});

test("실행 상태는 내부 코드 대신 화면 문구와 색으로 바꾼다", () => {
  expect(toHistoryRow(HISTORY_ITEM)).toMatchObject({
    key: RUN_ID,
    requestedAt: HISTORY_ITEM.requested_at,
    scenario: "PRODUCT_DESCRIPTION",
    modelCount: 2,
    status: { label: "일부 성공", tone: "yellow" },
    inactiveModelCount: 1,
  });
  expect(toHistoryRow({ ...HISTORY_ITEM, status: "FAILED" }).status.tone).toBe(
    "red",
  );
});

test("직접 작성 실행의 시나리오 칸은 Custom Prompt로 표시한다", () => {
  expect(
    toHistoryRow({ ...HISTORY_ITEM, test_type: "CUSTOM", scenario_code: null })
      .scenario,
  ).toBe("Custom Prompt");
});

test("상세는 당시 입력과 설정, 모델의 현재 상태를 함께 보여 준다", () => {
  const view = toHistoryDetail(RUN_DETAIL, RERUN_DRAFT);
  expect(view).toMatchObject({
    key: RUN_ID,
    input: {
      kind: "available",
      prompt: "과거 Prompt 원문",
      text: "저장한 입력",
      attachments: [],
    },
    models: [
      { name: "Mistral Nemo", provider: "DeepInfra", currentState: "active" },
      { name: "Nova Micro", provider: "Amazon", currentState: "inactive" },
    ],
  });
  expect(view.input).toHaveProperty(
    "schema",
    JSON.stringify({ type: "object" }, null, 2),
  );
  expect(view.settings).toEqual(
    expect.arrayContaining([
      { label: "테스트 유형", value: "기본 시나리오" },
      { label: "Temperature", value: "0.3" },
      { label: "최대 출력 토큰", value: "512" },
    ]),
  );
  expect(view.models.map((model) => model.key)).toHaveLength(
    new Set(view.models.map((model) => model.key)).size,
  );
});

test("값이 없는 입력은 빈 값으로, 없는 설정은 미기록으로 둔다", () => {
  const view = toHistoryDetail(RUN_DETAIL, {
    ...RERUN_DRAFT,
    input_text: null,
    json_schema: null,
    execution_config: {},
  });
  expect(view.input).toMatchObject({ text: "", schema: "" });
  expect(view.settings).toEqual(
    expect.arrayContaining([{ label: "Temperature", value: "미기록" }]),
  );
});

test("재실행 원본이 있는 실행만 원본 ID를 보여 준다", () => {
  const source = "01a1611f-3e80-73c5-a130-3efa5a1f75df";
  expect(
    toHistoryDetail(RUN_DETAIL, RERUN_DRAFT).settings.map((row) => row.label),
  ).not.toContain("재실행 원본 ID");
  expect(
    toHistoryDetail(
      {
        ...RUN_DETAIL,
        summary: { ...RUN_DETAIL.summary, rerun_of_simulation_id: source },
      },
      RERUN_DRAFT,
    ).settings,
  ).toContainEqual({ label: "재실행 원본 ID", value: source });
});

test("이미지를 구할 수 없는 실행은 접근 불가로 표시한다", () => {
  const assetId = "01a1611f-3e80-73c5-a130-3efa5a1f7700";
  const blocked = {
    ...RERUN_DRAFT,
    rerunnable: false,
    blocked_reason: "INPUT_MISSING" as const,
  };
  expect(
    toHistoryDetail(RUN_DETAIL, { ...blocked, asset_ids: [assetId] }).input,
  ).toMatchObject({
    attachments: [{ key: assetId, name: "이미지 1", available: false }],
  });
  expect(toHistoryDetail(RUN_DETAIL, blocked).input).toEqual({
    kind: "missing",
  });
});

test("이미지를 구할 수 있으면 첨부를 사용 가능으로 표시한다", () => {
  const assetId = "01a1611f-3e80-73c5-a130-3efa5a1f7700";
  expect(
    toHistoryDetail(RUN_DETAIL, { ...RERUN_DRAFT, asset_ids: [assetId] }).input,
  ).toMatchObject({
    attachments: [{ key: assetId, name: "이미지 1", available: true }],
  });
});

test("상세 상태는 없음·실패·로딩·완료를 구분한다", () => {
  const notFound = new ApiError(404, "NOT_FOUND", "없음");
  const failed = new ApiError(500, undefined, "실패");
  const empty = { data: undefined, error: null };
  const run = { data: RUN_DETAIL, error: null };
  const draft = { data: RERUN_DRAFT, error: null };
  expect(historyDetailState(empty, empty).kind).toBe("loading");
  expect(historyDetailState(run, empty).kind).toBe("loading");
  expect(
    historyDetailState({ data: undefined, error: notFound }, empty).kind,
  ).toBe("missing");
  expect(historyDetailState(run, { data: undefined, error: failed }).kind).toBe(
    "error",
  );
  expect(historyDetailState(run, draft).kind).toBe("ready");
});

test("폴링이 잠깐 실패해도 이미 받은 상세는 유지한다", () => {
  const failed = new ApiError(500, undefined, "실패");
  expect(
    historyDetailState(
      { data: RUN_DETAIL, error: failed },
      { data: RERUN_DRAFT, error: null },
    ).kind,
  ).toBe("ready");
});

test.each([
  ["PENDING", true],
  ["RUNNING", true],
  ["SUCCESS", false],
  ["PARTIAL_SUCCESS", false],
  ["FAILED", false],
  ["CANCELLED", false],
] as const)("%s 실행의 폴링 여부는 %s다", (status, expected) => {
  expect(isRunOngoing(status)).toBe(expected);
});
