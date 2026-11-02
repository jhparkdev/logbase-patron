import { zodResolver } from "@hookform/resolvers/zod";
import { useId } from "react";
import { useForm, useWatch } from "react-hook-form";
import { Button } from "../../../shared/components/ui/Button";
import { Dialog } from "../../../shared/components/ui/Dialog";
import {
  FIELD_TEXTAREA_CLASS,
  FormField,
  FormHint,
} from "../../../shared/components/ui/PanelForm";
import type { ModelRow } from "../api/models";
import { useRunConnectionTest } from "../hooks/useRunConnectionTest";
import {
  MAX_TEST_PROMPT_LENGTH,
  type TestPromptValues,
  testPromptFormSchema,
} from "../lib/testForm";
import { FormError } from "./FormError";
import { TestResultView } from "./TestResultView";

const PROMPT_ROWS = 4;
const RUN_FAILED_MESSAGE = "테스트를 실행하지 못했어요. 다시 시도해 주세요.";

type ConnectionTestDialogProps = {
  model: Pick<ModelRow, "model_id" | "display_name">;
  onClose: () => void;
};

/**
 * 연결 테스트 창. 실제 비용이 드는 호출이라 Prompt 입력과 비용 안내, 실행을 한 창에 모음.
 * 실행하면 같은 창에 결과를 보여 주고, 다시 하려면 닫았다 다시 연다.
 */
export function ConnectionTestDialog({
  model,
  onClose,
}: ConnectionTestDialogProps) {
  const run = useRunConnectionTest(model.model_id);
  const formId = useId();
  const {
    register,
    control,
    handleSubmit,
    formState: { errors },
  } = useForm<TestPromptValues>({
    defaultValues: { prompt: "" },
    resolver: zodResolver(testPromptFormSchema),
    reValidateMode: "onSubmit",
  });

  // 검증이 세는 값(앞뒤 공백 제외)과 같게 센다
  const promptLength = useWatch({ control, name: "prompt" }).trim().length;

  return (
    <Dialog
      open
      title="연결 테스트"
      onClose={onClose}
      action={
        run.data ? undefined : (
          // 누르는 즉시 비활성화해 같은 호출이 두 번 가지 않게 함
          <Button type="submit" form={formId} disabled={run.isPending}>
            {run.isPending ? "테스트 중" : "테스트 실행"}
          </Button>
        )
      }
    >
      {run.data ? (
        <TestResultView result={run.data} />
      ) : (
        <form
          id={formId}
          noValidate
          onSubmit={handleSubmit((values) => run.mutate(values.prompt))}
          className="flex flex-col gap-4"
        >
          <p>{model.display_name}에 AI 호출을 한 번 보내 연결을 확인해요.</p>
          <FormHint>
            실제 AI 호출이라 비용이 발생해요. Prompt를 비워 두면 기본 문장으로
            테스트해요.
          </FormHint>
          {run.isError && (
            <FormError error={run.error} fallback={RUN_FAILED_MESSAGE} />
          )}
          <FormField
            label="테스트 Prompt (선택)"
            error={errors.prompt?.message}
          >
            {(field) => (
              <>
                <textarea
                  rows={PROMPT_ROWS}
                  className={FIELD_TEXTAREA_CLASS}
                  {...field}
                  {...register("prompt")}
                />
                <p
                  className={`text-right text-caption tabular-nums ${promptLength > MAX_TEST_PROMPT_LENGTH ? "text-red-600" : "text-grey-600"}`}
                >
                  {promptLength}/{MAX_TEST_PROMPT_LENGTH}
                </p>
              </>
            )}
          </FormField>
        </form>
      )}
    </Dialog>
  );
}
