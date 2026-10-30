import { type ReactNode, useEffect, useId, useRef } from "react";
import closeIcon from "../../../assets/close.svg";
import { Icon } from "./Icon";

type SidePanelProps = {
  title: string;
  onClose: () => void;
  children: ReactNode;
};

/**
 * 화면 오른쪽에서 열리는 상세 패널. 열려 있는 동안 뒤 화면은 누를 수 없고,
 * 키보드 포커스는 패널 안에 머문다(브라우저 기본 모달 dialog).
 */
export function SidePanel({ title, onClose, children }: SidePanelProps) {
  const dialog = useRef<HTMLDialogElement>(null);
  const titleId = useId();
  useEffect(() => {
    dialog.current?.showModal();
  }, []);

  return (
    <dialog
      ref={dialog}
      aria-labelledby={titleId}
      // Esc로 닫을 때도 브라우저가 직접 닫지 않게 하고, 닫기는 쓰는 쪽(주소 변경)에 맡긴다.
      onCancel={(event) => {
        event.preventDefault();
        onClose();
      }}
      className="my-0 mr-0 ml-auto h-dvh max-h-none w-130 max-w-full bg-white text-grey-900 backdrop:bg-grey-900/50"
    >
      <div className="flex h-full flex-col">
        <header className="flex items-center justify-between gap-4 border-b border-grey-100 px-6 py-5">
          <h2 id={titleId} className="text-section font-bold">
            {title}
          </h2>
          <button
            type="button"
            aria-label="닫기"
            onClick={onClose}
            className="grid size-8 place-items-center rounded-lg text-grey-600 hover:bg-grey-100 focus-visible:outline-2 focus-visible:outline-brand"
          >
            <Icon src={closeIcon} className="size-3" />
          </button>
        </header>
        <div className="flex-1 overflow-y-auto px-6 py-5">{children}</div>
      </div>
    </dialog>
  );
}
