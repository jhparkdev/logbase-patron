import { expect, test } from "vitest";
import { MODEL_ROW } from "../../../test/modelsApi";
import { choiceKey, parseChoiceKey, toModelChoices } from "./catalog";

test("모델 하나를 서버 업체마다 고를 수 있는 항목으로 나눈다", () => {
  const choices = toModelChoices(MODEL_ROW, {
    providers: ["DeepInfra", "Io Net"],
  });
  expect(choices.map((choice) => choice.key)).toEqual([
    "3:DeepInfra",
    "3:Io Net",
  ]);
  expect(choices[0]).toMatchObject({
    name: "GPT-4o mini",
    provider: "DeepInfra",
    creator: "openai",
    selectable: true,
    supportsImages: true,
  });
});

test("모델 정보로 지원 설정과 입력 범위를 정한다", () => {
  const [choice] = toModelChoices(
    {
      ...MODEL_ROW,
      temperature_supported: true,
      reasoning_efforts: ["low", "high"],
      supports_json_schema: true,
    },
    { providers: ["DeepInfra"] },
  );
  expect(choice.supportedParameters).toEqual(
    expect.arrayContaining([
      "temperature",
      "max_tokens",
      "reasoning",
      "response_format",
    ]),
  );
  expect(choice.tuningParameters).toEqual([
    { key: "temperature", kind: "number", min: 0, max: 2, step: 0.01 },
    { key: "maxTokens", kind: "number", min: 1, max: 4096, step: 1 },
    {
      key: "reasoningEffort",
      kind: "choice",
      options: [
        { value: "low", label: "낮음" },
        { value: "high", label: "높음" },
      ],
    },
  ]);
});

test("받지 못하는 설정은 지원 목록에서 뺀다", () => {
  const [choice] = toModelChoices(
    {
      ...MODEL_ROW,
      input_modalities: ["text"],
      temperature_supported: false,
      reasoning_efforts: [],
      supports_json_schema: false,
    },
    { providers: ["DeepInfra"] },
  );
  expect(choice.supportsImages).toBe(false);
  expect(choice.supportedParameters).toEqual(["max_tokens"]);
  expect(choice.tuningParameters?.map((item) => item.key)).toEqual([
    "maxTokens",
  ]);
});

test.each([
  ["목록을 받지 못한 모델", { failed: true as const }],
  ["서버 업체가 없는 모델", { providers: [] }],
])("%s은 고를 수 없게 한 행으로 남긴다", (_name, state) => {
  const choices = toModelChoices(MODEL_ROW, state);
  expect(choices).toHaveLength(1);
  expect(choices[0]).toMatchObject({
    key: "3:",
    provider: "확인 불가",
    selectable: false,
    unavailableReason: "서버 업체를 확인할 수 없습니다",
  });
});

test.each([
  [3, "DeepInfra"],
  [12, "Provider:with:colon"],
])("선택 키에서 모델 %i과 업체 %s를 되찾는다", (modelId, provider) => {
  expect(parseChoiceKey(choiceKey(modelId, provider))).toEqual({
    model_id: modelId,
    execution_provider: provider,
  });
});

test.each(["", "abc", "3:", ":DeepInfra", "a:DeepInfra"])(
  "잘못된 선택 키 %s는 요청으로 만들지 않는다",
  (key) => {
    expect(parseChoiceKey(key)).toBeUndefined();
  },
);
