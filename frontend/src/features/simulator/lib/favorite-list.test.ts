import { describe, expect, test, vi } from "vitest";
import {
  favoriteKeys,
  findFavorite,
  toFavoritesView,
  withFavorite,
  withoutFavorite,
} from "./favorite-list";

const CREATED_AT = "2026-11-04T01:00:00Z";
const OPENAI = {
  model_id: 1,
  execution_provider: "OpenAI",
  created_at: CREATED_AT,
};
const AZURE = {
  model_id: 1,
  execution_provider: "Azure",
  created_at: CREATED_AT,
};

describe("favoriteKeys", () => {
  test("모델·Provider 조합을 모델 선택 항목의 key로 바꾼다", () => {
    expect(favoriteKeys([OPENAI, AZURE])).toEqual(["1:OpenAI", "1:Azure"]);
  });
});

describe("findFavorite", () => {
  test("key가 같은 항목을 찾고 없으면 undefined다", () => {
    expect(findFavorite([OPENAI, AZURE], "1:Azure")).toBe(AZURE);
    expect(findFavorite([OPENAI], "1:Azure")).toBeUndefined();
  });
});

describe("withFavorite", () => {
  test("없는 조합은 앞에 더한다", () => {
    expect(withFavorite([AZURE], OPENAI)).toEqual([OPENAI, AZURE]);
  });

  test("같은 조합이 이미 있으면 서버가 준 값으로 바꾸고 두 번 넣지 않는다", () => {
    const saved = { ...OPENAI, created_at: "2026-11-04T02:00:00Z" };
    expect(withFavorite([OPENAI, AZURE], saved)).toEqual([saved, AZURE]);
  });
});

describe("withoutFavorite", () => {
  test("해당 조합만 뺀다", () => {
    expect(withoutFavorite([OPENAI, AZURE], "1:OpenAI")).toEqual([AZURE]);
  });

  test("Provider 이름에 구분자가 있어도 조합 전체로 비교한다", () => {
    const colon = { ...OPENAI, execution_provider: "a:b" };
    expect(withoutFavorite([colon, OPENAI], "1:a:b")).toEqual([OPENAI]);
  });
});

describe("toFavoritesView", () => {
  const onSet = vi.fn();
  const onRetry = vi.fn();

  test("처음 불러오는 중이면 loading이다", () => {
    expect(toFavoritesView({ status: "pending", onSet, onRetry }).kind).toBe(
      "loading",
    );
  });

  test("불러오지 못했으면 다시 시도할 수 있는 error다", () => {
    expect(toFavoritesView({ status: "error", onSet, onRetry })).toEqual({
      kind: "error",
      onRetry,
    });
  });

  test("받은 목록과 저장 중·실패 항목을 함께 넘긴다", () => {
    expect(
      toFavoritesView({
        status: "success",
        items: [OPENAI],
        savingKeys: ["1:Azure"],
        failedKeys: ["2:Groq"],
        onSet,
        onRetry,
      }),
    ).toEqual({
      kind: "ready",
      keys: ["1:OpenAI"],
      savingKeys: ["1:Azure"],
      failedKeys: ["2:Groq"],
      onSet,
    });
  });
});
