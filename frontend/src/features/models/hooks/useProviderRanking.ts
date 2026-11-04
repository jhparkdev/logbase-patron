import { useSuspenseQuery } from "@tanstack/react-query";
import { providerRankingQuery } from "../api/models";
import { excludedText, rankingRows } from "../lib/ranking";

/** 모델의 서버 업체 순위. 불러오는 중이거나 실패하면 가장 가까운 DataBlock이 맡는다 */
export function useProviderRanking(modelId: number, cacheHitRatio: string) {
  const { data } = useSuspenseQuery(
    providerRankingQuery(modelId, cacheHitRatio),
  );
  return { rows: rankingRows(data), excluded: excludedText(data) };
}
