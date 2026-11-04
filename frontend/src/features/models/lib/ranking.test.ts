import { describe, expect, test } from "vitest";
import { RANKING } from "../../../test/modelsApi";
import {
  assumptionText,
  CACHE_CHOICES,
  DEFAULT_CACHE_CHOICE,
  excludedText,
  rankingRows,
} from "./ranking";

describe("rankingRows", () => {
  test("서버가 준 순서 그대로 보여 주고 첫 업체만 가장 저렴으로 표시한다", () => {
    expect(rankingRows(RANKING)).toEqual([
      { name: "DeepInfra", cost: "0.0021", cheapest: true, caching: true },
      { name: "Parasail", cost: "0.0035", cheapest: false, caching: false },
    ]);
  });

  test("업체가 하나뿐이면 가장 저렴이라고 표시하지 않는다", () => {
    const [only] = RANKING.items;

    expect(rankingRows({ items: [only], excluded: [] })[0].cheapest).toBe(
      false,
    );
  });

  test("아주 작은 비용도 0으로 보이지 않고 자릿수를 늘려 보여 준다", () => {
    const [first] = RANKING.items;
    const tiny = { ...first, expected_cost_usd: "0.0000012" };

    expect(rankingRows({ items: [tiny], excluded: [] })[0].cost).toBe(
      "0.0000012",
    );
  });

  test("순위가 비면 빈 목록이다", () => {
    expect(rankingRows({ items: [], excluded: [] })).toEqual([]);
  });
});

describe("excludedText", () => {
  test("빠진 업체와 이유를 한 줄로 알린다", () => {
    expect(
      excludedText({
        items: [],
        excluded: [
          { execution_provider: "Io Net", reason: "LOW_UPTIME" },
          { execution_provider: "Deka", reason: "PRICE_UNKNOWN" },
          { execution_provider: "Down", reason: "STATUS_NOT_OK" },
        ],
      }),
    ).toBe(
      "제외된 업체 3곳: Io Net(가동률 낮음), Deka(가격 미확인), Down(상태 이상)",
    );
  });

  test("빠진 업체가 없으면 알리지 않는다", () => {
    expect(excludedText({ items: [], excluded: [] })).toBeNull();
  });
});

test("가정 문구는 입력·출력 토큰 수를 밝힌다", () => {
  expect(assumptionText()).toBe(
    "입력 1,000 · 출력 500 토큰으로 작업 한 번을 처리할 때의 예상 비용이에요.",
  );
});

test("캐시 가정 선택지는 없음·절반·90%이고 기본은 절반이다", () => {
  expect(CACHE_CHOICES.map(({ value }) => value)).toEqual(["0", "0.5", "0.9"]);
  expect(DEFAULT_CACHE_CHOICE).toBe("0.5");
});
