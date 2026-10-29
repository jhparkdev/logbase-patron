import { type ReactNode, useEffect, useId, useRef } from "react";
import { Button } from "./Button";

export function Dialog({
  open,
  title,
  onClose,
  children,
  action,
  showTopClose = false,
}: {
  open: boolean;
  title: string;
  onClose: () => void;
  children: ReactNode;
  action?: ReactNode;
  showTopClose?: boolean;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const heading = useRef<HTMLHeadingElement>(null);
  const titleId = useId();
  useEffect(() => {
    const element = dialog.current;
    if (open && element && !element.open) {
      element.showModal();
      heading.current?.focus({ preventScroll: true });
      element.scrollTop = 0;
    }
    if (!open && element?.open) element.close();
  }, [open]);
  return (
    <dialog
      ref={dialog}
      aria-labelledby={titleId}
      onCancel={(event) => {
        if (event.target !== event.currentTarget) return;
        event.preventDefault();
        event.stopPropagation();
        onClose();
      }}
      className="fixed inset-0 m-auto max-h-4/5 w-3/4 max-w-4xl overflow-y-auto rounded-2xl bg-white p-6 text-grey-900 shadow-xl backdrop:bg-grey-900/40"
    >
      <div
        className={
          showTopClose
            ? "sticky top-0 z-10 -mx-6 -mt-6 mb-4 flex items-start justify-between gap-4 bg-white px-6 pt-6 pb-3"
            : "mb-4"
        }
      >
        <h2
          ref={heading}
          tabIndex={-1}
          id={titleId}
          className="min-w-0 text-section font-bold outline-none"
        >
          {title}
        </h2>
        {showTopClose && (
          <Button
            variant="secondary"
            size="sm"
            className="size-8"
            aria-label="창 닫기"
            title="닫기"
            onClick={onClose}
          >
            <span aria-hidden="true" className="text-section leading-none">
              ×
            </span>
          </Button>
        )}
      </div>
      {children}
      <div className="mt-6 flex justify-end gap-2">
        <Button variant="secondary" onClick={onClose}>
          닫기
        </Button>
        {action}
      </div>
    </dialog>
  );
}
