import { formatCount } from "../../../shared/lib/format";

/** 알림에 이름을 보여 주는 최근 모델 수 */
export const NEW_MODEL_NAME_COUNT = 3;

type NewModelsBody = {
  days: number;
  total: number;
  items: { name: string }[];
};

export type NewModelNoticeText = { title: string; description: string };

/** 새 모델 알림 문구. 새 모델이 없으면 null(알림을 보이지 않음) */
export function newModelsNotice(
  body: NewModelsBody,
): NewModelNoticeText | null {
  if (body.total <= 0) return null;
  const shown = body.items.slice(0, NEW_MODEL_NAME_COUNT);
  const rest = body.total - shown.length;
  const list = shown.map(({ name }) => name).join(", ");
  const tail = shown.length > 0 && rest > 0 ? ` 외 ${formatCount(rest)}개` : "";
  const intro = `최근 ${body.days}일 안에 올라왔어요.`;
  return {
    title: `새 모델 ${formatCount(body.total)}개가 올라왔어요`,
    description: shown.length > 0 ? `${intro} ${list}${tail}` : intro,
  };
}
