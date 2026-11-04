import type { components } from "../../../shared/api/schema";

type Item = components["schemas"]["ModelDiscoveryRead"];
type SkipReason = components["schemas"]["SkipReason"];

export type DiscoveryView = {
  key: string;
  name: string;
  label: string;
  tone: "green" | "grey" | "red";
  lines: string[];
};

const SKIP_LINES: Record<SkipReason, string> = {
  INITIAL: "처음 확인하기 전에 올라와 있던 모델이라 비교하지 않았어요",
  PRICE_TOO_HIGH:
    "단가가 기본 모델보다 많이 비싸거나 알 수 없어 비교하지 않았어요",
};

const BASE_PREFIX = "기본 모델 대비";

type Wording = { subject: string; same: string; less: string; more: string };

const COST: Wording = {
  subject: "비용",
  same: "비용이 같아요",
  less: "저렴해요",
  more: "비싸요",
};
const LATENCY: Wording = {
  subject: "응답",
  same: "응답 시간이 같아요",
  less: "빨라요",
  more: "느려요",
};

/** 증감률(음수면 줄었다) 문장. 모르면 null */
function changeLine(pct: string | null, wording: Wording): string | null {
  if (pct === null) return null;
  const size = pct.replace(/^-/, "");
  if (Number.parseFloat(size) === 0) return `${BASE_PREFIX} ${wording.same}`;
  const change = pct.startsWith("-") ? wording.less : wording.more;
  return `${BASE_PREFIX} ${wording.subject} ${size}% ${change}`;
}

function comparedView(item: Item): Omit<DiscoveryView, "key" | "name"> {
  const worth = item.cheaper === true || item.faster === true;
  const unknown = item.cheaper === null && item.faster === null;
  return {
    label: worth
      ? "확인해 볼 만해요"
      : unknown
        ? "비교하지 못했어요"
        : "기본 모델이 더 좋거나 비슷해요",
    tone: worth ? "green" : "grey",
    lines: [
      changeLine(item.cost_change_pct, COST) ?? "비용은 알 수 없어요",
      changeLine(item.latency_change_pct, LATENCY) ??
        "응답 시간은 알 수 없어요",
    ],
  };
}

export function discoveryView(item: Item): DiscoveryView {
  const base = { key: item.openrouter_model_id, name: item.name };
  if (item.status === "COMPARED") return { ...base, ...comparedView(item) };
  if (item.status === "SKIPPED") {
    return {
      ...base,
      label: "비교하지 않았어요",
      tone: "grey",
      lines: item.skip_reason ? [SKIP_LINES[item.skip_reason]] : [],
    };
  }
  if (item.status === "FAILED")
    return { ...base, label: "비교에 실패했어요", tone: "red", lines: [] };
  return {
    ...base,
    label: "비교를 기다려요",
    tone: "grey",
    lines: ["기본 모델과 비용 여유가 준비되면 비교해요"],
  };
}
