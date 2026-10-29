import type { ReactNode } from "react";
import warningIcon from "../../../assets/warning.svg";
import { Icon } from "./Icon";

type NoticeProps = {
  title: string;
  description: string;
  /** 오른쪽 끝의 이동 링크나 버튼 */
  action?: ReactNode;
};

/** 화면 위쪽에서 확인이 필요한 일을 알리는 띠. 예: 미분류 사용 내역 */
export function Notice({ title, description, action }: NoticeProps) {
  return (
    <div className="flex items-center gap-4 rounded-2xl bg-blue-50 px-6 py-4">
      <Icon src={warningIcon} className="size-5 text-blue-600" />
      <div className="flex min-w-0 flex-1 flex-wrap items-baseline gap-x-6 gap-y-1">
        <p className="font-semibold">{title}</p>
        <p className="text-body-sm text-grey-700">{description}</p>
      </div>
      {action}
    </div>
  );
}
