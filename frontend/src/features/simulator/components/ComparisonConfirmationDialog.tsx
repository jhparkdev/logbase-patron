import { Button } from "../../../shared/components/ui/Button";
import type { SimulatorDraft } from "../lib/form";
import { PARAMETER_LABELS, type ParameterKey } from "../lib/parameters";
import {
  appliedSettings,
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
      title="비교를 실행합니다"
      onClose={onClose}
      action={
        <Button disabled={busy} onClick={onConfirm}>
          실행하기
        </Button>
      }
    >
      <p className="text-body-sm text-grey-700">
        선택한 {draft?.comparisons.length}개 비교 항목을 실행하며 비용이 발생할
        수 있습니다. 취소 후에도 이미 처리된 호출에는 비용이 청구될 수 있습니다.
      </p>
      <ul aria-label="실행할 비교 항목" className="mt-4 space-y-2 text-body-sm">
        {draft?.comparisons.map((comparison, index) => {
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
            .map((key) => `${PARAMETER_LABELS[key]}: ${settings[key]}`);
          return (
            <li
              key={comparison.comparisonId}
              className="rounded-lg bg-grey-50 px-3 py-2"
            >
              <p className="font-semibold">
                비교 항목 {index + 1} · {choice?.name} · {choice?.provider}
              </p>
              <p className="mt-1 text-caption text-grey-600">
                요청 설정: {labels.length ? labels.join(" · ") : "기본값 사용"}
              </p>
            </li>
          );
        })}
      </ul>
    </SimulatorDialog>
  );
}
