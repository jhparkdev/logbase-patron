import { expect, test } from "vitest";
import { creatorBadge } from "./creator";
import { searchModels } from "./model-selection";

test("제작사 표기는 명시된 값만 사용하고 대소문자와 공백으로 색상이 달라지지 않는다", () => {
  expect(creatorBadge(" MistralAI ")).toMatchObject({ label: "MistralAI" });
  expect(creatorBadge(" MistralAI ").tone).toBe(creatorBadge("mistralai").tone);
  expect(creatorBadge("mistralai").tone).not.toBe(creatorBadge("google").tone);
});

test("제작사 정보가 없으면 미확인 배지를 쓰고 새 제작사 이름은 그대로 보존한다", () => {
  expect(creatorBadge()).toEqual({ label: "제작사 미확인", tone: "grey" });
  expect(creatorBadge("  ")).toEqual(creatorBadge());
  expect(creatorBadge("새 제작사").label).toBe("새 제작사");
});

test("제작사로도 모델을 찾되 실행 Provider를 제작사로 대체하지 않는다", () => {
  const model = {
    key: "2:DeepInfra",
    name: "모델 A",
    provider: "DeepInfra",
    creator: "mistralai",
    selectable: true,
    supportsImages: false,
    supportedParameters: [],
  };
  expect(searchModels([model], "MISTRALAI DeepInfra")).toEqual([model]);
  expect(searchModels([{ ...model, creator: undefined }], "mistralai")).toEqual(
    [],
  );
});
