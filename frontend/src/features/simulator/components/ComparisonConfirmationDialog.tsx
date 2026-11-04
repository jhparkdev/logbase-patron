import { Badge } from "../../../shared/components/ui/Badge";
import { Button } from "../../../shared/components/ui/Button";
import { inputSummary, unitPriceLabel } from "../lib/card-view";
import type { SimulatorDraft } from "../lib/form";
import { PARAMETER_LABELS, type ParameterKey } from "../lib/parameters";
import {
  appliedSettings,
  droppedSettingsNote,
  type ModelChoice,
  type ScenarioChoice,
} from "../lib/presentation";
import { SimulatorDialog } from "./SimulatorDialog";

export function ComparisonConfirmationDialog({
  draft,
  choices,
  scenarios,
  busy,
  onClose,
  onConfirm,
}: {
  draft?: SimulatorDraft;
  choices: ModelChoice[];
  scenarios: ScenarioChoice[];
  busy: boolean;
  onClose: () => void;
  onConfirm: () => void;
}) {
  const scenario =
    draft?.mode === "scenario"
      ? scenarios.find((item) => item.key === draft.scenarioKey)
      : undefined;
  return (
    <SimulatorDialog
      open={!!draft}
      title="비교를 실행할까요?"
      onClose={onClose}
      action={
        <Button disabled={busy} onClick={onConfirm}>
          실행하기
        </Button>
      }
    >
      <p className="text-body-sm text-grey-700">
        모델{" "}
        <strong className="tabular-nums">{draft?.comparisons.length}</strong>
        개를 호출해요. 호출마다 비용이 발생하고, 취소해도 이미 처리된 호출은
        비용이 청구될 수 있어요.
      </p>
      <p className="mt-4 text-caption font-semibold text-grey-600">
        전송할 모델과 설정
      </p>
      <ul aria-label="실행할 비교 항목" className="mt-2 space-y-2">
        {draft?.comparisons.map((comparison) => {
          const choice = choices.find(
            (item) => item.key === comparison.modelKey,
          );
          // 공통 끔과 받지 못해 빠지는 항목을 반영한, 실제로 보낼 값을 보여 준다.
          const settings = choice
            ? appliedSettings(comparison, draft, choice, scenario)
            : {};
          const labels = (
            ["temperature", "maxTokens", "reasoningEffort"] as ParameterKey[]
          )
            .filter((key) => settings[key] !== undefined)
            .map((key) => `${PARAMETER_LABELS[key]} ${settings[key]}`);
          const note = choice
            ? droppedSettingsNote(comparison, draft, choice, scenario)
            : undefined;
          const price = unitPriceLabel(choice?.price);
          return (
            <li
              key={comparison.comparisonId}
              className="flex items-center justify-between gap-3 rounded-lg bg-grey-50 px-3 py-2.5"
            >
              <div className="min-w-0">
                <p className="flex flex-wrap items-center gap-1.5 text-body-sm font-semibold">
                  {choice?.name}
                  <span className="font-normal text-grey-600">
                    · {choice?.provider}
                  </span>
                  {comparison.settings.mode === "custom" && (
                    <Badge tone="blue">개별 설정</Badge>
                  )}
                </p>
                <p className="mt-0.5 text-caption text-grey-600 tabular-nums">
                  {labels.length ? labels.join(" · ") : "기본값 사용"}
                </p>
                {note && (
                  <p className="mt-0.5 text-caption text-grey-600">{note}</p>
                )}
              </div>
              <span className="shrink-0 text-caption text-grey-600 tabular-nums">
                {price ? (
                  <>
                    {price} <span className="text-grey-500">USD/1M</span>
                  </>
                ) : (
                  <Badge tone="yellow">단가 미확인</Badge>
                )}
              </span>
            </li>
          );
        })}
      </ul>
      {draft && (
        <div className="mt-4 flex flex-col gap-1 border-t border-grey-100 pt-3.5">
          <p className="text-caption font-semibold text-grey-600">입력</p>
          <p className="text-body-sm tabular-nums">
            {inputSummary({
              prompt: draft.prompt,
              text: draft.text,
              imageCount: draft.files.length + draft.existingAssetIds.length,
              jsonSchema: draft.jsonSchema,
            })}
          </p>
          <p className="text-caption text-grey-600">
            단가는 모델 관리의 최신 확인값이에요. 실제 비용은 실행 뒤 토큰 수로
            확정돼요.
          </p>
        </div>
      )}
    </SimulatorDialog>
  );
}
