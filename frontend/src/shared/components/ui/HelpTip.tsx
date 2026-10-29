import { useId } from "react";
import tipIcon from "../../../assets/tip.svg";
import { Icon } from "./Icon";

/** 라벨 옆 물음표. 마우스를 올리거나 키보드로 옮기면 설명을 보여 준다. */
export function HelpTip({ text }: { text: string }) {
  const tooltipId = useId();
  return (
    <span className="group relative inline-flex">
      <button
        type="button"
        aria-label="도움말"
        aria-describedby={tooltipId}
        className="rounded-full text-grey-500 hover:text-grey-700 focus-visible:outline-2 focus-visible:outline-brand"
      >
        <Icon src={tipIcon} className="size-3.5" />
      </button>
      <span
        role="tooltip"
        id={tooltipId}
        className="invisible absolute bottom-full left-1/2 z-10 mb-2 w-max max-w-60 -translate-x-1/2 rounded-lg bg-grey-800 px-3 py-2 text-caption font-medium text-white group-focus-within:visible group-hover:visible"
      >
        {text}
      </span>
    </span>
  );
}
