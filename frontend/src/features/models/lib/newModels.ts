import { formatCount } from "../../../shared/lib/format";

type NewModelsBody = {
  days: number;
  total: number;
};

export type NewModelNoticeText = { title: string; description: string };

/**
 * 새 모델 알림 문구. 새 모델이 없으면 null(알림을 보이지 않음).
 * 어떤 모델인지는 알리지 않는다. 신규 모델 등록 패널에서 확인한다.
 */
export function newModelsNotice(
  body: NewModelsBody,
): NewModelNoticeText | null {
  if (body.total <= 0) return null;
  return {
    title: `새 모델 ${formatCount(body.total)}개가 올라왔어요`,
    description: `최근 ${body.days}일 안에 OpenRouter에 올라왔어요.`,
  };
}
