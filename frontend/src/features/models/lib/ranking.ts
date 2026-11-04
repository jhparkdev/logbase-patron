import type { components } from "../../../shared/api/schema";
import { formatCount, formatUsd } from "../../../shared/lib/format";

type Ranking = components["schemas"]["ProviderRankingResponse"];
type ExcludedReason = components["schemas"]["ExcludedReason"];

/** 순위를 계산할 때 가정하는 작업 한 번의 토큰 수. 화면에 그대로 밝힌다 */
export const RANKING_INPUT_TOKENS = 1000;
export const RANKING_OUTPUT_TOKENS = 500;

/** 입력 중 캐시에서 읽는 비율의 선택지. 값은 서버로 보내는 0~1 비율이다 */
export const CACHE_CHOICES = [
  { value: "0", label: "캐시 없음" },
  { value: "0.5", label: "입력의 절반을 캐시에서 읽음" },
  { value: "0.9", label: "입력의 90%를 캐시에서 읽음" },
];
export const DEFAULT_CACHE_CHOICE = "0.5";

const EXCLUDED_LABELS: Record<ExcludedReason, string> = {
  STATUS_NOT_OK: "상태 이상",
  LOW_UPTIME: "가동률 낮음",
  PRICE_UNKNOWN: "가격 미확인",
};

export function assumptionText(): string {
  return `입력 ${formatCount(RANKING_INPUT_TOKENS)} · 출력 ${formatCount(RANKING_OUTPUT_TOKENS)} 토큰으로 작업 한 번을 처리할 때의 예상 비용이에요.`;
}

/** 순위의 한 줄. 서버가 이미 싼 순서로 정렬해 주므로 다시 정렬하지 않는다 */
export function rankingRows(ranking: Ranking) {
  return ranking.items.map((item, index) => ({
    name: item.execution_provider,
    cost: formatUsd(item.expected_cost_usd, "perCall"),
    // 비교 대상이 하나뿐이면 가장 저렴이라는 말이 의미가 없다
    cheapest: index === 0 && ranking.items.length > 1,
    caching: item.supports_caching,
  }));
}

/** 순위에서 빠진 업체와 이유. 빠진 업체가 없으면 null */
export function excludedText(ranking: Ranking): string | null {
  if (ranking.excluded.length === 0) return null;
  const list = ranking.excluded
    .map(
      ({ execution_provider, reason }) =>
        `${execution_provider}(${EXCLUDED_LABELS[reason]})`,
    )
    .join(", ");
  return `제외된 업체 ${ranking.excluded.length}곳: ${list}`;
}
