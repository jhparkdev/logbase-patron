import { useState } from "react";
import editIcon from "../../../assets/edit.svg";
import { Icon } from "../../../shared/components/ui/Icon";
import { InfoEditForm, type InfoFormProps } from "./InfoEditForm";

const NO_VALUE_LABEL = "미입력";

/** 글자 + 연필이 기본. 연필을 누르면 이 항목만 입력 칸으로 바뀌고, 저장·취소하면 글자로 돌아옴 */
export function EditableInfoRow(props: InfoFormProps) {
  const [editing, setEditing] = useState(false);
  if (editing) {
    return <InfoEditForm {...props} onDone={() => setEditing(false)} />;
  }
  return (
    <>
      <dt className="text-grey-600">{props.label}</dt>
      <dd className="flex items-center gap-1.5">
        {props.value ?? <span className="text-grey-600">{NO_VALUE_LABEL}</span>}
        <button
          type="button"
          aria-label={`${props.label} 수정`}
          onClick={() => setEditing(true)}
          className="grid size-6 place-items-center rounded-lg text-grey-600 hover:bg-grey-100 focus-visible:outline-2 focus-visible:outline-brand"
        >
          <Icon src={editIcon} className="size-3.5" />
        </button>
      </dd>
    </>
  );
}
