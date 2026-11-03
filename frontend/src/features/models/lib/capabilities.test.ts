import { expect, test } from "vitest";
import { capabilityTags, contextCaption } from "./capabilities";

const ALL: Parameters<typeof capabilityTags>[0] = {
  input_modalities: ["text", "image"],
  output_modalities: ["text"],
  supports_json_schema: true,
  supports_tools: true,
  temperature_supported: true,
  reasoning_efforts: ["low", "high"],
};

test("입출력 형식 한 줄 뒤에 기능 네 개를 태그로 나열한다", () => {
  expect(capabilityTags(ALL)).toEqual([
    { key: "modalities", label: "텍스트·이미지 → 텍스트", supported: true },
    { key: "json", label: "JSON 스키마", supported: true },
    { key: "tools", label: "함수 호출", supported: true },
    { key: "temperature", label: "Temperature 조절", supported: true },
    { key: "reasoning", label: "추론 강도 조절", supported: true },
  ]);
});

test("지원하지 않는 기능도 빼지 않고 미지원으로 남긴다", () => {
  const tags = capabilityTags({
    ...ALL,
    supports_json_schema: false,
    supports_tools: false,
    temperature_supported: false,
    reasoning_efforts: [],
  });
  expect(tags.map((tag) => tag.supported)).toEqual([
    true,
    false,
    false,
    false,
    false,
  ]);
});

test("Context Length는 토큰 단위로, 모르면 0이 아니라 미확인이다", () => {
  expect(contextCaption(128000)).toBe("Context 128,000 토큰");
  expect(contextCaption(null)).toBe("Context 미확인");
});
