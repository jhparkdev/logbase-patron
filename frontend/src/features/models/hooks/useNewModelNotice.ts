import { useQuery } from "@tanstack/react-query";
import { newOpenRouterModelsQuery } from "../api/models";
import { type NewModelNoticeText, newModelsNotice } from "../lib/newModels";

/**
 * 새 모델 알림 문구. 부가 정보라서 불러오는 중이거나 실패했거나
 * 새 모델이 없으면 null(알림을 보이지 않음).
 */
export function useNewModelNotice(): NewModelNoticeText | null {
  const { data } = useQuery(newOpenRouterModelsQuery);
  return data ? newModelsNotice(data) : null;
}
