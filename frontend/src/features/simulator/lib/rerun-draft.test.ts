import { expect, test } from "vitest";
import { RERUN_DRAFT, RUN_ID } from "../../../test/simulationHistoryApi";
import { rerunRestoreView, toRerunValues } from "./rerun-draft";

const custom = {
  ...RERUN_DRAFT,
  test_type: "CUSTOM" as const,
  scenario_id: null,
};

test("과거 입력과 공통 설정, 모델 칸을 폼 값으로 되돌린다", () => {
  const values = toRerunValues(custom);
  expect(values).toMatchObject({
    mode: "custom",
    prompt: "과거 Prompt 원문",
    text: "저장한 입력",
    jsonSchema: JSON.stringify({ type: "object" }, null, 2),
    temperature: "0.3",
    maxTokens: "512",
    reasoningEffort: "",
  });
  expect(values.comparisons?.map((item) => item.modelKey)).toEqual([
    "2:DeepInfra",
    "4:Amazon",
  ]);
});

test("공통 설정과 같은 칸은 공통을 따르고 다른 칸만 칸 설정으로 되돌린다", () => {
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
  expect(values.comparisons?.[0].settings.mode).toBe("shared");
  expect(values.comparisons?.[1].settings).toEqual({
    mode: "custom",
    temperature: "0",
    maxTokens: "512",
    reasoningEffort: "low",
  });
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

const ready = { draft: custom, catalogReady: true, error: null };

test("초안과 모델 목록이 모두 있어야 복원한다", () => {
  expect(
    rerunRestoreView({ ...ready, draft: undefined }, RUN_ID, []).kind,
  ).toBe("loading");
  expect(
    rerunRestoreView({ ...ready, catalogReady: false }, RUN_ID, []).kind,
  ).toBe("loading");
  expect(rerunRestoreView(ready, RUN_ID, [])).toMatchObject({
    kind: "ready",
    key: RUN_ID,
  });
});

test("시나리오 실행은 직접 작성으로 바꾸지 않고 복원을 막는다", () => {
  expect(
    rerunRestoreView({ ...ready, draft: RERUN_DRAFT }, RUN_ID, []).kind,
  ).toBe("scenario");
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
