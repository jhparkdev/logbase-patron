import { expect, test } from "vitest";
import {
  RERUN_DRAFT,
  RUN_ID,
  SCENARIO,
} from "../../../test/simulationHistoryApi";
import { simulatorFormSchema } from "./form";
import { toCreateRequest } from "./request";
import { rerunRestoreView, toRerunValues } from "./rerun-draft";

const custom = {
  ...RERUN_DRAFT,
  test_type: "CUSTOM" as const,
  scenario_id: null,
  output_type: "TEXT" as const,
};

test("과거 입력과 공통 설정, 모델 칸을 폼 값으로 되돌린다", () => {
  const values = toRerunValues(custom);
  expect(values).toMatchObject({
    mode: "custom",
    prompt: "과거 Prompt 원문",
    text: "저장한 입력",
    jsonSchema: JSON.stringify({ type: "object" }, null, 2),
    commonEnabled: false,
    temperature: "0.3",
    maxTokens: "512",
    reasoningEffort: "",
  });
  expect(values.comparisons?.map((item) => item.modelKey)).toEqual([
    "2:DeepInfra",
    "4:Amazon",
  ]);
});

test("텍스트 실행은 공통 설정을 끄고 칸마다 실제 적용값을 개별 지정으로 되돌린다", () => {
  const [first, second] = custom.models;
  const values = toRerunValues({
    ...custom,
    models: [
      { ...first, execution_config: { temperature: 0.3, max_tokens: 512 } },
      {
        ...second,
        execution_config: {
          temperature: 0,
          max_tokens: 512,
          reasoning_effort: "low",
        },
      },
    ],
  });
  expect(values.commonEnabled).toBe(false);
  expect(values.comparisons?.map((item) => item.settings)).toEqual([
    {
      mode: "custom",
      temperature: "0.3",
      maxTokens: "512",
      reasoningEffort: "",
    },
    {
      mode: "custom",
      temperature: "0",
      maxTokens: "512",
      reasoningEffort: "low",
    },
  ]);
});

test("적용값이 없던 칸은 기본값을 따르게 둔다", () => {
  const [first, second] = custom.models;
  const values = toRerunValues({
    ...custom,
    models: [
      { ...first, execution_config: {} },
      { ...second, execution_config: { temperature: 0.3 } },
    ],
  });
  expect(values.comparisons?.map((item) => item.settings.mode)).toEqual([
    "shared",
    "custom",
  ]);
});

test("복원한 값으로 다시 만든 요청은 원래 실행의 칸별 적용값과 같다", () => {
  const [first, second] = custom.models;
  const original = {
    ...custom,
    models: [
      { ...first, execution_config: { temperature: 0.3, max_tokens: 512 } },
      {
        ...second,
        execution_config: {
          temperature: 0,
          max_tokens: 512,
          reasoning_effort: "low",
        },
      },
    ],
  };
  const request = toCreateRequest(
    simulatorFormSchema.parse(toRerunValues(original)),
    [],
    original.rerun_of_simulation_id,
  );
  expect(request.execution_config).toBeNull();
  expect(
    request.models.map((model) => [
      model.model_id,
      model.execution_provider,
      model.execution_config,
    ]),
  ).toEqual(
    original.models.map((model) => [
      model.model_id,
      model.execution_provider,
      model.execution_config,
    ]),
  );
});

test("Schema와 입력이 없던 실행은 빈 칸으로 되돌리고 이미지는 ID로 유지한다", () => {
  const assetId = "01a1611f-3e80-73c5-a130-3efa5a1f7700";
  expect(
    toRerunValues({
      ...custom,
      input_text: null,
      json_schema: null,
      asset_ids: [assetId],
    }),
  ).toMatchObject({ text: "", jsonSchema: "", existingAssetIds: [assetId] });
});

const ready = {
  draft: custom,
  catalogReady: true,
  error: null,
  scenarios: [SCENARIO],
  scenariosFailed: false,
};

test("초안과 모델 목록, 시나리오 목록이 모두 있어야 복원한다", () => {
  expect(
    rerunRestoreView({ ...ready, draft: undefined }, RUN_ID, []).kind,
  ).toBe("loading");
  expect(
    rerunRestoreView({ ...ready, catalogReady: false }, RUN_ID, []).kind,
  ).toBe("loading");
  expect(
    rerunRestoreView({ ...ready, scenarios: undefined }, RUN_ID, []).kind,
  ).toBe("loading");
  expect(rerunRestoreView(ready, RUN_ID, [])).toMatchObject({
    kind: "ready",
    key: RUN_ID,
  });
});

test("시나리오 실행은 실행 유형과 시나리오를 그대로 되돌린다", () => {
  expect(toRerunValues(RERUN_DRAFT)).toMatchObject({
    mode: "scenario",
    scenarioKey: "3",
    prompt: "과거 Prompt 원문",
  });
  expect(toRerunValues(custom)).toMatchObject({
    mode: "custom",
    scenarioKey: "",
  });
});

test("지금은 비활성인 원본 시나리오도 복원 선택지에 남긴다", () => {
  const view = rerunRestoreView(
    {
      ...ready,
      draft: RERUN_DRAFT,
      scenarios: [
        { ...SCENARIO, is_active: false },
        { ...SCENARIO, scenario_id: 9, is_active: false },
      ],
    },
    RUN_ID,
    [],
  );
  expect(view).toMatchObject({ kind: "ready", scenarios: [{ key: "3" }] });
});

test("시나리오 목록을 받지 못하면 시나리오 실행을 직접 작성으로 바꾸지 않고 멈춘다", () => {
  const failed = { ...ready, scenarios: undefined, scenariosFailed: true };
  expect(
    rerunRestoreView({ ...failed, draft: RERUN_DRAFT }, RUN_ID, []).kind,
  ).toBe("error");
  // 직접 작성 실행은 시나리오가 필요 없으므로 복원한다
  expect(rerunRestoreView(failed, RUN_ID, [])).toMatchObject({
    kind: "ready",
    scenarios: [],
  });
});

test("입력을 구할 수 없는 실행은 복원하지 않는다", () => {
  expect(
    rerunRestoreView(
      {
        ...ready,
        draft: {
          ...custom,
          rerunnable: false,
          blocked_reason: "INPUT_MISSING",
        },
      },
      RUN_ID,
      [],
    ).kind,
  ).toBe("missing");
});
