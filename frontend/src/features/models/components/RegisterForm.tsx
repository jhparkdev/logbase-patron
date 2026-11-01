import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { Button } from "../../../shared/components/ui/Button";
import {
  FIELD_INPUT_CLASS,
  FormField,
  FormHint,
} from "../../../shared/components/ui/PanelForm";
import type { OpenRouterModel } from "../api/models";
import { useRegisterModel } from "../hooks/useRegisterModel";
import { type RegisterFormValues, registerFormSchema } from "../lib/infoForm";
import { FormError } from "./FormError";

const REGISTER_FAILED_MESSAGE = "등록하지 못했어요. 다시 시도해 주세요.";

type RegisterFormProps = {
  /** 고른 OpenRouter 모델. 표시 이름의 처음 값으로 이름을 씀 */
  model: OpenRouterModel;
  onClose: () => void;
};

/** 신규 등록 정보 입력. 등록하면 항상 검증 중(TESTING) 상태로 시작 */
export function RegisterForm({ model, onClose }: RegisterFormProps) {
  const register = useRegisterModel();
  const {
    register: field,
    handleSubmit,
    formState: { errors },
  } = useForm<RegisterFormValues>({
    defaultValues: { displayName: model.name, purpose: "" },
    resolver: zodResolver(registerFormSchema),
    reValidateMode: "onSubmit",
  });

  return (
    <form
      noValidate
      onSubmit={handleSubmit((values) =>
        register.mutate(
          {
            openrouter_model_id: model.openrouter_model_id,
            display_name: values.displayName,
            purpose: values.purpose,
          },
          { onSuccess: onClose },
        ),
      )}
      className="flex flex-col gap-4"
    >
      <h3 className="font-bold">2. 등록 정보</h3>
      {register.isError && (
        <FormError error={register.error} fallback={REGISTER_FAILED_MESSAGE} />
      )}
      <div className="flex flex-col gap-1.5">
        <span className="text-label font-medium text-grey-700">Model ID</span>
        <p className="flex h-9.5 items-center rounded-control bg-grey-100 px-3 text-body-sm text-grey-700">
          {model.openrouter_model_id}
        </p>
      </div>
      <FormField label="표시 이름" error={errors.displayName?.message}>
        {(control) => (
          <input
            className={FIELD_INPUT_CLASS}
            {...control}
            {...field("displayName")}
          />
        )}
      </FormField>
      <FormField label="용도 (선택)" error={errors.purpose?.message}>
        {(control) => (
          <input
            className={FIELD_INPUT_CLASS}
            placeholder="예: 고객 문의 요약 비교용"
            {...control}
            {...field("purpose")}
          />
        )}
      </FormField>
      <FormHint>
        등록하면 '검증 중' 상태로 시작해요. 연결 테스트에 성공한 뒤 '사용
        중'으로 바꿀 수 있어요.
      </FormHint>
      <div className="flex justify-end gap-2">
        <Button variant="secondary" onClick={onClose}>
          닫기
        </Button>
        {/* 누르는 즉시 비활성화해 같은 등록이 두 번 가지 않게 함 */}
        <Button type="submit" disabled={register.isPending}>
          등록
        </Button>
      </div>
    </form>
  );
}
