import { formatCount } from "../../../shared/lib/format";

type NewModelsBody = {
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
    title: "새로운 모델이 나왔어요",
    description: `아직 등록하지 않은 모델 ${formatCount(body.total)}개가 있어요.`,
  };
}

/** 가장 새 모델이 마지막으로 확인한 시각보다 뒤에 올라왔는지. 확인한 값을 읽을 수 없으면 아직 안 본 것으로 본다 */
export function hasUnseenNewModels(
  latest: string | null,
  seen: string | null,
): boolean {
  if (latest === null) return false;
  const seenAt = seen === null ? Number.NaN : Date.parse(seen);
  return Number.isNaN(seenAt) || Date.parse(latest) > seenAt;
}
