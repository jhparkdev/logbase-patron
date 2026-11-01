const PALETTE = ["blue", "green", "yellow", "red"] as const;
const CREATOR_TONES = new Map<string, (typeof PALETTE)[number]>([
  ["moonshotai", "blue"],
  ["mistralai", "red"],
  ["google", "green"],
  ["amazon", "yellow"],
]);

export function creatorBadge(creator?: string) {
  const label = creator?.trim();
  if (!label) return { label: "제작사 미확인", tone: "grey" as const };
  const key = label.toLocaleLowerCase();
  // 목록 순서가 바뀌거나 새 제작사가 추가되어도 기존 색은 유지한다.
  let hash = 0;
  for (const character of key)
    hash = (hash * 31 + character.charCodeAt(0)) >>> 0;
  return {
    label,
    tone: CREATOR_TONES.get(key) ?? PALETTE[hash % PALETTE.length],
  };
}
