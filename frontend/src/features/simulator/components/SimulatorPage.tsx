import { FormProvider } from "react-hook-form";
import { Button } from "../../../shared/components/ui/Button";
import { Notice } from "../../../shared/components/ui/Notice";
import { PageHeader } from "../../../shared/components/ui/PageHeader";
import { Result } from "../../../shared/components/ui/Result";
import { Skeleton } from "../../../shared/components/ui/Skeleton";
import { useSimulatorForm } from "../hooks/useSimulatorForm";
import type { ModelFavoritesView } from "../lib/favorites";
import type { SimulatorDraft, SimulatorFormValues } from "../lib/form";
import type { ModelChoice, ScenarioChoice } from "../lib/presentation";
import { AdvancedSettings } from "./AdvancedSettings";
import { InputFields } from "./InputFields";
import { ModelSelection } from "./ModelSelection";
import {
  SimulationResults,
  type SimulationResultsProps,
} from "./SimulationResults";
import { SimulatorDialog } from "./SimulatorDialog";

type SimulatorPageProps = Partial<SimulationResultsProps> & {
  choices?: ModelChoice[];
  scenarios?: ScenarioChoice[];
  catalogState?: "ready" | "loading" | "error" | "unavailable";
  onRetryCatalog?: () => void;
  onRun?: (draft: SimulatorDraft) => void | Promise<void>;
  initialValues?: Partial<SimulatorFormValues>;
  favorites?: ModelFavoritesView;
};

export function SimulatorPage({
  choices = [],
  scenarios = [],
  catalogState,
  onRetryCatalog,
  onRun,
  initialValues,
  favorites,
  view = { kind: "empty" },
  ...resultProps
}: SimulatorPageProps) {
  const state = catalogState ?? (choices.length ? "ready" : "unavailable");
  const workflow = useSimulatorForm({
    choices,
    scenarios,
    onRun,
    initialValues,
    running: view.kind === "ready" && !!view.run.status.ongoing,
  });
  return (
    <>
      <PageHeader title="AI 모델 시뮬레이터" />
      {!onRun && (
        <Notice
          title="비교 실행을 준비하고 있습니다"
          description="입력과 설정을 편집할 수 있습니다. 실행 기능이 준비되면 모델을 선택해 비교할 수 있습니다."
        />
      )}
      <FormProvider {...workflow.form}>
        <form
          noValidate
          onSubmit={workflow.submit}
          className="rounded-2xl bg-white p-6"
        >
          <fieldset disabled={workflow.busy || !!workflow.pendingDraft}>
            <legend className="sr-only">시뮬레이션 입력 및 비교 설정</legend>
            <InputFields scenarios={scenarios} />
            <AdvancedSettings
              open={workflow.advancedOpen}
              onToggle={() => workflow.setAdvancedOpen(!workflow.advancedOpen)}
              scenario={workflow.selectedScenario}
            />
            {state === "loading" && (
              <div className="border-t border-grey-100 py-4">
                <p role="status" className="mb-3 text-body-sm text-grey-600">
                  모델 목록을 불러오고 있습니다
                </p>
                <Skeleton className="h-12 w-full" />
              </div>
            )}
            {state === "error" && (
              <Result
                title="모델 목록을 불러오지 못했습니다"
                description="잠시 후 다시 시도하시기 바랍니다."
                action={
                  onRetryCatalog && (
                    <Button variant="secondary" onClick={onRetryCatalog}>
                      다시 시도
                    </Button>
                  )
                }
              />
            )}
            {state === "ready" && !choices.some((item) => item.selectable) && (
              <Result
                title="선택할 수 있는 모델이 없습니다"
                description="AI 모델 관리에서 활성 모델을 확인하시기 바랍니다."
              />
            )}
            <ModelSelection
              choices={choices}
              unavailable={state !== "ready"}
              favorites={favorites}
            />
            {workflow.issues.length > 0 && (
              <div
                role="alert"
                className="mt-4 rounded-lg bg-danger-weak p-3 text-body-sm text-red-600"
              >
                <ul className="list-inside list-disc">
                  {workflow.issues.map((issue) => (
                    <li key={issue}>{issue}</li>
                  ))}
                </ul>
              </div>
            )}
            <div className="mt-5 flex items-center justify-between gap-4">
              <p className="text-caption text-grey-600">
                같은 Prompt와 입력으로 비교합니다. 실행 전 비용 발생 여부를
                확인하시기 바랍니다.
              </p>
              <Button
                type="submit"
                disabled={!workflow.canRun || state !== "ready"}
              >
                {workflow.submitting ? "실행 요청 중" : "비교 실행"}
              </Button>
            </div>
          </fieldset>
        </form>
      </FormProvider>
      <SimulationResults view={view} {...resultProps} />
      <SimulatorDialog
        open={!!workflow.pendingDraft}
        title="비교를 실행합니다"
        onClose={() => workflow.setPendingDraft(undefined)}
        action={
          <Button
            disabled={workflow.busy}
            onClick={() => void workflow.confirm()}
          >
            실행하기
          </Button>
        }
      >
        <p className="text-body-sm text-grey-700">
          선택한 {workflow.pendingDraft?.selections.length}개 모델을 호출하며
          비용이 발생할 수 있습니다. 취소 후에도 이미 처리된 호출에는 비용이
          청구될 수 있습니다.
        </p>
        <ul className="mt-4 space-y-2 text-body-sm">
          {workflow.pendingDraft?.selections.map((key) => {
            const choice = choices.find((item) => item.key === key);
            return (
              <li key={key} className="rounded-lg bg-grey-50 px-3 py-2">
                {choice?.name} · {choice?.provider}
              </li>
            );
          })}
        </ul>
      </SimulatorDialog>
    </>
  );
}
