import { type ReactNode, useEffect, useId, useRef } from "react";
import { Button } from "../../../shared/components/ui/Button";

export function SimulatorDialog({
  open,
  title,
  onClose,
  children,
  action,
}: {
  open: boolean;
  title: string;
  onClose: () => void;
  children: ReactNode;
  action?: ReactNode;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const titleId = useId();
  useEffect(() => {
    const element = dialog.current;
    if (open && !element?.open) element?.showModal();
    if (!open && element?.open) element.close();
  }, [open]);
  return (
    <dialog
      ref={dialog}
      aria-labelledby={titleId}
      onCancel={(event) => {
        event.preventDefault();
        onClose();
      }}
      className="fixed inset-0 m-auto max-h-4/5 w-3/4 max-w-4xl overflow-y-auto rounded-2xl bg-white p-6 text-grey-900 shadow-xl backdrop:bg-grey-900/40"
    >
      <h2 id={titleId} className="mb-4 text-section font-bold">
        {title}
      </h2>
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
