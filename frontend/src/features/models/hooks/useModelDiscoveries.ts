import { useQuery } from "@tanstack/react-query";
import { modelDiscoveriesQuery } from "../api/models";
import { type DiscoveryView, discoveryView } from "../lib/discoveries";

/** 새 모델 비교 결과. 부가 정보라서 불러오는 중이거나 실패하면 빈 목록(보이지 않음) */
export function useModelDiscoveries(): DiscoveryView[] {
  const { data } = useQuery(modelDiscoveriesQuery);
  return data ? data.items.map(discoveryView) : [];
}
