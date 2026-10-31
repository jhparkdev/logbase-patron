import { type ReactNode, useId } from "react";
import { Button } from "../../../shared/components/ui/Button";

// 상세 패널 폼이 함께 쓰는 조각: 입력 칸 모양, 라벨·검증 문구, 안내 상자, 아래 버튼 줄

const FIELD_BOX_CLASS =
  "w-full rounded-control border border-neutral-weak bg-grey-50 px-3 text-body-sm focus-visible:border-brand focus-visible:outline-none aria-invalid:border-red-500";
/** 한 줄 입력 칸. 잘못된 입력이면 빨간 테두리를 그린다. */
export const FIELD_INPUT_CLASS = `h-9.5 ${FIELD_BOX_CLASS}`;
/** 여러 줄 입력 칸. 높이는 rows로 정한다. */
export const FIELD_TEXTAREA_CLASS = `py-2.5 ${FIELD_BOX_CLASS}`;

type FieldControlProps = {
  id: string;
  "aria-invalid": boolean;
  "aria-describedby"?: string;
};

type FormFieldProps = {
  label: string;
  /** 검증 문구. 있으면 칸 아래에 보여 주고 칸과 연결한다. */
  error?: string;
  /** 입력 칸을 그린다. 받은 속성(id, 잘못된 입력 표시)을 입력 칸에 그대로 넘긴다. */
  children: (control: FieldControlProps) => ReactNode;
};

/** 라벨 + 입력 칸 + 검증 문구. 라벨과 문구를 입력 칸에 연결한다. */
export function FormField({ label, error, children }: FormFieldProps) {
  const id = useId();
  const errorId = useId();
  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={id} className="text-label font-medium text-grey-700">
        {label}
      </label>
      {children({
        id,
        "aria-invalid": error !== undefined,
        "aria-describedby": error === undefined ? undefined : errorId,
      })}
      {error !== undefined && (
        <p id={errorId} className="text-label font-medium text-red-600">
          {error}
        </p>
      )}
    </div>
  );
}

/** 입력 전에 알아 둘 규칙을 알리는 회색 상자 */
export function FormHint({ children }: { children: ReactNode }) {
  return (
    <p className="rounded-xl bg-grey-50 p-3 text-label text-grey-700">
      {children}
    </p>
  );
}

type FormActionsProps = {
  submitLabel: string;
  /** false면 저장할 API가 아직 없어 제출 버튼을 막는다. */
  canSubmit: boolean;
  onClose: () => void;
};

/** 폼 아래 버튼 줄. 물러나는 쪽은 "닫기"다. */
export function FormActions({
  submitLabel,
  canSubmit,
  onClose,
}: FormActionsProps) {
  return (
    <div className="flex justify-end gap-2">
      <Button variant="secondary" onClick={onClose}>
        닫기
      </Button>
      <Button type="submit" disabled={!canSubmit}>
        {submitLabel}
      </Button>
    </div>
  );
}
