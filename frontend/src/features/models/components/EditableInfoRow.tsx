import { useState } from "react";
import editIcon from "../../../assets/edit.svg";
import { FIELD_CLASS } from "../../../shared/components/ui/fieldStyle";
import { Icon } from "../../../shared/components/ui/Icon";
import { InfoEditForm, type InfoFormProps } from "./InfoEditForm";

const NO_VALUE_LABEL = "미입력";

/** 라벨 + 입력 칸 모양의 읽기 상자. 상자 안 연필을 누르면 입력 칸으로 바뀌고, 저장·취소하면 돌아옴 */
export function EditableInfoRow(props: InfoFormProps) {
  const [editing, setEditing] = useState(false);
  if (editing) {
    return <InfoEditForm {...props} onDone={() => setEditing(false)} />;
  }
  return (
    <div className="flex flex-col gap-1.5">
      <span className="text-label font-medium text-grey-700">
        {props.label}
      </span>
      <div
        className={`${FIELD_CLASS} flex items-center justify-between gap-2 pr-1.5 pl-3`}
      >
        {props.value ?? <span className="text-grey-600">{NO_VALUE_LABEL}</span>}
        <button
          type="button"
          aria-label={`${props.label} 수정`}
          onClick={() => setEditing(true)}
          className="grid size-6 shrink-0 place-items-center rounded-lg text-grey-600 hover:bg-grey-100 focus-visible:outline-2 focus-visible:outline-brand"
        >
          <Icon src={editIcon} className="size-3.5" />
        </button>
      </div>
    </div>
  );
}
