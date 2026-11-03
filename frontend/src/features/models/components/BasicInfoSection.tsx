import lockIcon from "../../../assets/lock.svg";
import { FIELD_CLASS } from "../../../shared/components/ui/fieldStyle";
import { Icon } from "../../../shared/components/ui/Icon";
import type { ModelDetail } from "../api/models";
import { capabilityTags, contextCaption } from "../lib/capabilities";
import { displayNameFormSchema, purposeFormSchema } from "../lib/infoForm";
import { CapabilityTags } from "./CapabilityTags";
import { EditableInfoRow } from "./EditableInfoRow";

const READ_BOX_CLASS = `${FIELD_CLASS} flex items-center gap-2 px-3`;

/** 표시 이름·용도는 연필로 수정. Model ID·Provider는 OpenRouter 값이라 고칠 수 없음 */
export function BasicInfoSection({ model }: { model: ModelDetail }) {
  return (
    <div className="flex flex-col gap-4">
      <EditableInfoRow
        modelId={model.model_id}
        field="display_name"
        label="표시 이름"
        value={model.display_name}
        schema={displayNameFormSchema}
      />
      <EditableInfoRow
        modelId={model.model_id}
        field="purpose"
        label="용도"
        value={model.purpose}
        schema={purposeFormSchema}
      />
      <dl className="grid grid-cols-2 gap-4">
        <div className="flex flex-col gap-1.5">
          <dt className="text-label font-medium text-grey-700">Model ID</dt>
          <dd className={`${READ_BOX_CLASS} justify-between text-grey-700`}>
            <span className="truncate">{model.openrouter_model_id}</span>
            <Icon src={lockIcon} className="size-3.5 text-grey-500" />
          </dd>
        </div>
        <div className="flex flex-col gap-1.5">
          <dt className="text-label font-medium text-grey-700">Provider</dt>
          <dd className={READ_BOX_CLASS}>
            <span
              aria-hidden="true"
              className="grid size-6 shrink-0 place-items-center rounded-full border border-grey-200 bg-white text-caption font-bold uppercase"
            >
              {model.provider.charAt(0)}
            </span>
            <span className="truncate">{model.provider}</span>
          </dd>
        </div>
      </dl>
      <div className="flex flex-col gap-2">
        <p className="text-label font-medium text-grey-700">
          지원 기능 · {contextCaption(model.context_length)}
        </p>
        <CapabilityTags tags={capabilityTags(model)} />
      </div>
    </div>
  );
}
