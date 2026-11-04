import type { BadgeTone } from "../../../shared/components/ui/Badge";

// 고정 색이 없는 제작사가 해시로 받는 팔레트. `grey`는 "제작사 미확인", `white`는 openai에만 쓴다.
export const CREATOR_TONES = [
  "orange",
  "teal",
  "blue",
  "purple",
  "red",
  "yellow",
  "green",
] as const satisfies readonly BadgeTone[];
// 브랜드를 연상시키는 색으로 고정한다. 근거는 docs/design/tokens.md "제작사 배지".
const FIXED_TONES = new Map<string, BadgeTone>([
  ["anthropic", "orange"],
  ["openai", "white"],
  ["google", "blue"],
  ["meta-llama", "purple"],
  ["mistralai", "red"],
  ["amazon", "yellow"],
  ["nvidia", "green"],
]);

export function creatorBadge(creator?: string): {
  label: string;
  tone: BadgeTone;
} {
  const label = creator?.trim();
  if (!label) return { label: "제작사 미확인", tone: "grey" };
  const key = label.toLocaleLowerCase();
  // 고정 색이 없는 제작사는 이름 해시로 정해, 목록 순서가 바뀌거나 새 제작사가 추가되어도 기존 색은 유지한다.
  let hash = 0;
  for (const character of key)
    hash = (hash * 31 + character.charCodeAt(0)) >>> 0;
  return {
    label,
    tone: FIXED_TONES.get(key) ?? CREATOR_TONES[hash % CREATOR_TONES.length],
  };
}
