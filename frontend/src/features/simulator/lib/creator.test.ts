import { expect, test } from "vitest";
import { CREATOR_TONES, creatorBadge } from "./creator";
import { searchModels } from "./model-selection";

test("제작사 표기는 명시된 값만 사용하고 대소문자와 공백으로 색상이 달라지지 않는다", () => {
  expect(creatorBadge(" MistralAI ")).toMatchObject({ label: "MistralAI" });
  expect(creatorBadge(" MistralAI ").tone).toBe(creatorBadge("mistralai").tone);
  expect(creatorBadge("mistralai").tone).not.toBe(creatorBadge("google").tone);
});

test("주요 제작사는 브랜드를 연상시키는 고정 색을 받는다", () => {
  expect(creatorBadge("anthropic").tone).toBe("orange");
  expect(creatorBadge("OpenAI").tone).toBe("white");
  expect(creatorBadge("google").tone).toBe("blue");
  expect(creatorBadge("meta-llama").tone).toBe("purple");
  expect(creatorBadge("mistralai").tone).toBe("red");
  expect(creatorBadge("Amazon").tone).toBe("yellow");
  expect(creatorBadge("nvidia").tone).toBe("green");
});

test("고정 색을 받는 제작사끼리는 색이 겹치지 않는다", () => {
  const tones = CREATOR_PALETTE_SAMPLE.map((name) => creatorBadge(name).tone);
  expect(new Set(tones).size).toBe(tones.length);
});

test("고정 색이 없는 제작사는 제작사 팔레트 안에서 색을 받고 미확인용 회색은 쓰지 않는다", () => {
  for (const name of ["deepseek", "z-ai", "moonshotai", "새 제작사"]) {
    const { tone } = creatorBadge(name);
    expect(tone).not.toBe("grey");
    expect(CREATOR_TONES).toContain(tone);
  }
});

const CREATOR_PALETTE_SAMPLE = [
  "anthropic",
  "openai",
  "google",
  "meta-llama",
  "mistralai",
  "amazon",
  "nvidia",
];

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
