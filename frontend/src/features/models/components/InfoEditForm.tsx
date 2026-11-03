import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import type { z } from "zod";
import { Button } from "../../../shared/components/ui/Button";
import {
  FIELD_INPUT_CLASS,
  FormField,
} from "../../../shared/components/ui/PanelForm";
import { useUpdateModelInfo } from "../hooks/useUpdateModelInfo";
import type { InfoFormValues } from "../lib/infoForm";
import { FormError } from "./FormError";

const SAVE_FAILED_MESSAGE = "저장하지 못했어요. 다시 시도해 주세요.";

export type InfoField = "display_name" | "purpose";

export type InfoFormProps = {
  modelId: number;
  /** 서버로 보낼 항목 이름 */
  field: InfoField;
  label: string;
  /** 저장된 값. 입력 칸의 처음 값 */
  value: string | null;
  schema: z.ZodType<InfoFormValues, InfoFormValues>;
};

/** 한 항목 수정 폼. 저장을 누를 때만 검증하고, 저장에 성공하면 onDone으로 글자 보기로 돌아감 */
export function InfoEditForm({
  modelId,
  field,
  label,
  value,
  schema,
  onDone,
}: InfoFormProps & { onDone: () => void }) {
  const save = useUpdateModelInfo(modelId);
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<InfoFormValues>({
    defaultValues: { value: value ?? "" },
    resolver: zodResolver(schema),
    reValidateMode: "onSubmit",
  });

  return (
    <form
      noValidate
      onSubmit={handleSubmit((values) =>
        save.mutate({ [field]: values.value }, { onSuccess: onDone }),
      )}
      className="flex flex-col gap-3"
    >
      {save.isError && (
        <FormError error={save.error} fallback={SAVE_FAILED_MESSAGE} />
      )}
      <FormField label={label} error={errors.value?.message}>
        {(control) => (
          <input
            className={FIELD_INPUT_CLASS}
            {...control}
            {...register("value")}
          />
        )}
      </FormField>
      <div className="flex justify-end gap-2">
        <Button variant="secondary" onClick={onDone}>
          취소
        </Button>
        <Button type="submit" disabled={save.isPending}>
          저장
        </Button>
      </div>
    </form>
  );
}
