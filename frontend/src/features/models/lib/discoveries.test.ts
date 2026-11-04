import { expect, test } from "vitest";
import type { components } from "../../../shared/api/schema";
import { discoveryView } from "./discoveries";

type Item = components["schemas"]["ModelDiscoveryRead"];

const BASE: Item = {
  openrouter_model_id: "acme/new",
  name: "Acme: New",
  discovered_at: "2026-11-05T01:00:00Z",
  status: "COMPARED",
  skip_reason: null,
  base_model_name: "기본 모델",
  new_cost_usd: "0.0005",
  base_cost_usd: "0.001",
  new_latency_ms: 800,
  base_latency_ms: 1000,
  cost_change_pct: "-50.0",
  latency_change_pct: "-20.0",
  cheaper: true,
  faster: true,
};

test("싸고 빠르면 확인해 볼 만하다고 초록으로 알린다", () => {
  expect(discoveryView(BASE)).toEqual({
    key: "acme/new",
    name: "Acme: New",
    label: "확인해 볼 만해요",
    tone: "green",
    lines: [
      "기본 모델 대비 비용 50.0% 저렴해요",
      "기본 모델 대비 응답 20.0% 빨라요",
    ],
  });
});

test("더 비싸고 느리면 확인해 볼 만하지 않다고 회색으로 알린다", () => {
  const view = discoveryView({
    ...BASE,
    cost_change_pct: "30.0",
    latency_change_pct: "10.0",
    cheaper: false,
    faster: false,
  });

  expect(view.label).toBe("기본 모델이 더 좋거나 비슷해요");
  expect(view.tone).toBe("grey");
  expect(view.lines).toEqual([
    "기본 모델 대비 비용 30.0% 비싸요",
    "기본 모델 대비 응답 10.0% 느려요",
  ]);
});

test("값을 모르면 0이 아니라 미확인이라고 알린다", () => {
  const view = discoveryView({
    ...BASE,
    new_cost_usd: null,
    cost_change_pct: null,
    cheaper: null,
  });

  expect(view.lines[0]).toBe("비용은 알 수 없어요");
  expect(view.tone).toBe("green");
});

test("비용과 시간을 모두 모르면 비교하지 못했다고 알린다", () => {
  const view = discoveryView({
    ...BASE,
    cost_change_pct: null,
    latency_change_pct: null,
    cheaper: null,
    faster: null,
  });

  expect(view.label).toBe("비교하지 못했어요");
  expect(view.tone).toBe("grey");
});

test("증감이 없으면 같다고 알린다", () => {
  const view = discoveryView({
    ...BASE,
    cost_change_pct: "0.0",
    cheaper: false,
    faster: false,
    latency_change_pct: "0.0",
  });

  expect(view.lines).toEqual([
    "기본 모델 대비 비용이 같아요",
    "기본 모델 대비 응답 시간이 같아요",
  ]);
});

test.each([
  ["INITIAL", "처음 확인하기 전에 올라와 있던 모델이라 비교하지 않았어요"],
  [
    "PRICE_TOO_HIGH",
    "단가가 기본 모델보다 많이 비싸거나 알 수 없어 비교하지 않았어요",
  ],
] as const)("넘어간 이유 %s를 문장으로 알린다", (reason, line) => {
  const view = discoveryView({
    ...BASE,
    status: "SKIPPED",
    skip_reason: reason,
    base_model_name: null,
    cost_change_pct: null,
    latency_change_pct: null,
    cheaper: null,
    faster: null,
  });

  expect(view.label).toBe("비교하지 않았어요");
  expect(view.lines).toEqual([line]);
});

test("대기 중인 모델과 실패한 모델은 상태만 알린다", () => {
  const empty = {
    ...BASE,
    base_model_name: null,
    cost_change_pct: null,
    latency_change_pct: null,
    cheaper: null,
    faster: null,
  };

  expect(discoveryView({ ...empty, status: "PENDING" })).toMatchObject({
    label: "비교를 기다려요",
    tone: "grey",
    lines: ["기본 모델과 비용 여유가 준비되면 비교해요"],
  });
  expect(discoveryView({ ...empty, status: "FAILED" })).toMatchObject({
    label: "비교에 실패했어요",
    tone: "red",
  });
});
