import type { ReactNode } from "react";
import warningIcon from "../../../assets/warning.svg";
import { Icon } from "./Icon";

// 파랑은 알림, 노랑은 확인이 필요한 경고(예: 미분류 사용 내역)
const TONE_CLASS = {
  blue: { box: "bg-blue-50", icon: "text-blue-600" },
  yellow: { box: "bg-yellow-50", icon: "text-yellow-900" },
} as const;

type NoticeProps = {
  title: string;
  description: string;
  /** 오른쪽 끝의 이동 링크나 버튼 */
  action?: ReactNode;
  tone?: keyof typeof TONE_CLASS;
};

/** 화면 위쪽에서 확인이 필요한 일을 알리는 띠. */
export function Notice({
  title,
  description,
  action,
  tone = "blue",
}: NoticeProps) {
  const toneClass = TONE_CLASS[tone];
  return (
    <div
      className={`flex items-center gap-4 rounded-2xl px-6 py-4 ${toneClass.box}`}
    >
      <Icon src={warningIcon} className={`size-5 ${toneClass.icon}`} />
      <div className="flex min-w-0 flex-1 flex-wrap items-baseline gap-x-6 gap-y-1">
        <p className="font-semibold">{title}</p>
        <p className="text-body-sm text-grey-700">{description}</p>
      </div>
      {action}
    </div>
  );
}
