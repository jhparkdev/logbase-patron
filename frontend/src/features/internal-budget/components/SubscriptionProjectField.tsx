import {
  type Control,
  Controller,
  type FieldErrors,
  type UseFormRegister,
  useWatch,
} from "react-hook-form";
import {
  FIELD_INPUT_CLASS,
  FormField,
} from "../../../shared/components/ui/PanelForm";
import { Select } from "../../../shared/components/ui/Select";
import type { SubscriptionProject } from "../api/budget";
import type { SubscriptionFormInput } from "../lib/forms";
import { NEW_PROJECT_VALUE } from "../lib/newProject";

/** 아직 프로젝트를 고르지 않은 상태를 보여 주는 안내 항목. 고른 채로는 등록되지 않는다. */
const PLACEHOLDER_OPTION = { value: "", label: "프로젝트를 골라 주세요" };
/** 선택지에 없는 프로젝트를 화면을 떠나지 않고 만들어 바로 귀속한다 */
const NEW_PROJECT_OPTION = {
  value: NEW_PROJECT_VALUE,
  label: "새 프로젝트 추가…",
};

type SubscriptionProjectFieldProps = {
  control: Control<SubscriptionFormInput>;
  register: UseFormRegister<SubscriptionFormInput>;
  errors: FieldErrors<SubscriptionFormInput>;
  /** 선택지를 아직 못 받았으면 상자만 비활성이다. */
  projects?: SubscriptionProject[];
  /** 프로젝트가 비어 있을 수 있는 폼(등록, 옛 미배분 구독료 수정)에만 안내 항목을 둔다. 있는 프로젝트는 비울 수 없다. */
  withPlaceholder: boolean;
};

/** 귀속 프로젝트 선택 상자. "새 프로젝트 추가…"를 고르면 이름 칸이 나온다. */
export function SubscriptionProjectField({
  control,
  register,
  errors,
  projects,
  withPlaceholder,
}: SubscriptionProjectFieldProps) {
  const project = useWatch({ control, name: "project" });
  return (
    <>
      <div className="flex flex-col gap-1.5">
        <Controller
          control={control}
          name="project"
          render={({ field }) => (
            <Select
              label="귀속 프로젝트"
              labelPosition="top"
              value={field.value}
              options={[
                ...(withPlaceholder ? [PLACEHOLDER_OPTION] : []),
                ...(projects ?? []).map((item) => ({
                  value: String(item.project_id),
                  label: item.name,
                })),
                NEW_PROJECT_OPTION,
              ]}
              onChange={field.onChange}
              disabled={projects === undefined}
              className="w-full"
            />
          )}
        />
        {errors.project && (
          <p className="text-label font-medium text-red-600">
            {errors.project.message}
          </p>
        )}
      </div>
      {project === NEW_PROJECT_VALUE && (
        <FormField
          label="새 프로젝트 이름"
          error={errors.newProjectName?.message}
        >
          {(field) => (
            <input
              className={FIELD_INPUT_CLASS}
              {...field}
              {...register("newProjectName")}
            />
          )}
        </FormField>
      )}
    </>
  );
}
