import { useState } from "react";
import { FormProvider, useWatch } from "react-hook-form";
import { Button } from "../../../shared/components/ui/Button";
import { Notice } from "../../../shared/components/ui/Notice";
import { PageHeader } from "../../../shared/components/ui/PageHeader";
import { Result } from "../../../shared/components/ui/Result";
import { Skeleton } from "../../../shared/components/ui/Skeleton";
import { useSimulatorForm } from "../hooks/useSimulatorForm";
import { inputSummary, runBlockReason } from "../lib/card-view";
import type { ModelFavoritesView } from "../lib/favorites";
import type { SimulatorDraft, SimulatorFormValues } from "../lib/form";
import { IMAGE_LIMITS, type ImageLimits } from "../lib/limits";
import type { ModelChoice, ScenarioChoice } from "../lib/presentation";
import { AdvancedSettings } from "./AdvancedSettings";
import { ComparisonConfirmationDialog } from "./ComparisonConfirmationDialog";
import { InputFields } from "./InputFields";
import { ModelSelection } from "./ModelSelection";
import { RunBar } from "./RunBar";
import { RunConditionSummary } from "./RunConditionSummary";
import {
  SimulationResults,
  type SimulationResultsProps,
} from "./SimulationResults";

export type SimulatorPageProps = Partial<SimulationResultsProps> & {
  imageLimits?: ImageLimits;
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
  imageLimits = IMAGE_LIMITS,
  view = { kind: "empty" },
  ...resultProps
}: SimulatorPageProps) {
  const state = catalogState ?? (choices.length ? "ready" : "unavailable");
  const running = view.kind === "ready" && !!view.run.status.ongoing;
  // 이 화면에서 실행한 뒤에만 폼을 요약으로 접어 결과를 위로 올린다. 조건을 고치려면 다시 펼친다.
  // 주소로 결과만 열었을 때는 폼이 비어 있으므로 접지 않는다.
  const [editing, setEditing] = useState(true);
  const workflow = useSimulatorForm({
    choices,
    scenarios,
    onRun:
      onRun &&
      (async (draft) => {
        await onRun(draft);
        setEditing(false);
      }),
    initialValues,
    imageLimits,
    running,
  });
  const [prompt, text, files, existingAssetIds, jsonSchema, comparisons] =
    useWatch({
      control: workflow.form.control,
      name: [
        "prompt",
        "text",
        "files",
        "existingAssetIds",
        "jsonSchema",
        "comparisons",
      ],
    });
  const collapsed = view.kind === "ready" && !editing && prompt.trim() !== "";
  const modelCount = comparisons.filter((item) => item.modelKey).length;
  const notice =
    state === "loading" ? (
      <div>
        <p role="status" className="mb-3 text-body-sm text-grey-600">
          모델 목록을 불러오고 있어요
        </p>
        <Skeleton className="h-12 w-full" />
      </div>
    ) : state === "error" ? (
      <Result
        title="모델 목록을 불러오지 못했어요"
        description="잠시 후 다시 시도해 주세요."
        action={
          onRetryCatalog && (
            <Button variant="secondary" onClick={onRetryCatalog}>
              다시 시도
            </Button>
          )
        }
      />
    ) : state === "ready" && !choices.some((item) => item.selectable) ? (
      <Result
        title="고를 수 있는 모델이 없어요"
        description="AI 모델 관리에서 활성 모델을 확인해 주세요."
      />
    ) : undefined;
  return (
    <>
      <PageHeader
        title="AI 모델 시뮬레이터"
        description="같은 Prompt와 입력으로 모델 2~4개를 한 번에 비교해요."
      />
      {!onRun && (
        <Notice
          title="비교 실행을 준비하고 있어요"
          description="입력과 설정은 편집할 수 있어요. 실행 기능이 준비되면 모델을 골라 비교할 수 있어요."
        />
      )}
      <FormProvider {...workflow.form}>
        <form
          noValidate
          onSubmit={workflow.submit}
          className="flex flex-col gap-6"
        >
          <fieldset
            disabled={workflow.busy || !!workflow.pendingDraft}
            className="flex min-w-0 flex-col gap-6"
          >
            <legend className="sr-only">시뮬레이션 입력 및 비교 설정</legend>
            {collapsed ? (
              <RunConditionSummary
                scenarios={scenarios}
                running={running}
                onEdit={() => setEditing(true)}
              />
            ) : (
              <>
                <InputFields scenarios={scenarios} imageLimits={imageLimits} />
                <ModelSelection
                  choices={choices}
                  scenarios={scenarios}
                  unavailable={state !== "ready"}
                  favorites={favorites}
                  settings={
                    <AdvancedSettings
                      choices={choices}
                      open={workflow.advancedOpen}
                      onToggle={() =>
                        workflow.setAdvancedOpen(!workflow.advancedOpen)
                      }
                      scenario={workflow.selectedScenario}
                    />
                  }
                  notice={notice}
                />
                <RunBar
                  summary={inputSummary({
                    prompt,
                    text,
                    imageCount: files.length + existingAssetIds.length,
                    jsonSchema,
                  })}
                  modelCount={modelCount}
                  reason={
                    state === "ready" ? runBlockReason(modelCount) : undefined
                  }
                  issues={workflow.issues}
                  disabled={!workflow.canRun || state !== "ready"}
                  submitting={workflow.submitting}
                />
              </>
            )}
          </fieldset>
        </form>
      </FormProvider>
      <SimulationResults view={view} {...resultProps} />
      <ComparisonConfirmationDialog
        draft={workflow.pendingDraft}
        choices={choices}
        scenarios={scenarios}
        busy={workflow.busy}
        onClose={() => workflow.setPendingDraft(undefined)}
        onConfirm={() => void workflow.confirm()}
      />
    </>
  );
}
