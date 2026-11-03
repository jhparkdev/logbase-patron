import { expect, test } from "vitest";
import { createComparisons } from "./comparisons";
import { createDefaultValues, simulatorFormSchema } from "./form";
import { toCreateRequest } from "./request";

const ASSET = "01a1611f-3e80-73c5-a130-3efa5a1f7700";
const SOURCE = "01a1611f-3e80-73c5-a130-3efa5a1f75de";

function draft(overrides: Parameters<typeof createDefaultValues>[0] = {}) {
  return simulatorFormSchema.parse(
    createDefaultValues({
      prompt: "원문을 보존해 주세요. ",
      comparisons: createComparisons(["2:DeepInfra", "3:DekaLLM"]),
      ...overrides,
    }),
  );
}

test("직접 작성 실행을 API 요청으로 바꾼다", () => {
  expect(toCreateRequest(draft(), [])).toEqual({
    test_type: "CUSTOM",
    prompt_text: "원문을 보존해 주세요. ",
    input_text: null,
    json_schema: null,
    execution_config: {},
    models: [
      { model_id: 2, execution_provider: "DeepInfra", execution_config: {} },
      { model_id: 3, execution_provider: "DekaLLM", execution_config: {} },
    ],
    asset_ids: [],
    output_type: "TEXT",
  });
});

test("공통 설정과 입력, Schema, 이미지, 재실행 원본을 함께 보낸다", () => {
  const request = toCreateRequest(
    draft({
      text: "입력",
      jsonSchema: '{"type":"object"}',
      temperature: "0",
      maxTokens: "512",
      reasoningEffort: "low",
      existingAssetIds: [ASSET],
    }),
    ["01a1611f-3e80-73c5-a130-3efa5a1f7701"],
    SOURCE,
  );
  expect(request).toMatchObject({
    input_text: "입력",
    json_schema: { type: "object" },
    execution_config: {
      temperature: 0,
      max_tokens: 512,
      reasoning_effort: "low",
    },
    asset_ids: [ASSET, "01a1611f-3e80-73c5-a130-3efa5a1f7701"],
    rerun_of_simulation_id: SOURCE,
  });
});

test("칸에 직접 넣은 설정만 그 칸의 설정으로 보낸다", () => {
  const [first, second] = createComparisons(["2:DeepInfra", "2:DekaLLM"]);
  const request = toCreateRequest(
    draft({
      temperature: "0.5",
      comparisons: [
        first,
        {
          ...second,
          settings: {
            mode: "custom",
            temperature: "0.9",
            maxTokens: "",
            reasoningEffort: "",
          },
        },
      ],
    }),
    [],
  );
  expect(request.execution_config).toEqual({ temperature: 0.5 });
  expect(request.models.map((model) => model.execution_config)).toEqual([
    {},
    { temperature: 0.9 },
  ]);
});

test("서버 업체를 알 수 없는 칸이 있으면 요청을 만들지 않는다", () => {
  expect(() =>
    toCreateRequest(
      draft({ comparisons: createComparisons(["3:", "2:DeepInfra"]) }),
      [],
    ),
  ).toThrow();
});
