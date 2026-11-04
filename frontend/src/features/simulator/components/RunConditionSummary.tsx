import { useFormContext, useWatch } from "react-hook-form";
import { Badge } from "../../../shared/components/ui/Badge";
import { Button } from "../../../shared/components/ui/Button";
import { inputSummary } from "../lib/card-view";
import type { SimulatorDraft, SimulatorFormValues } from "../lib/form";
import { PARAMETER_LABELS } from "../lib/parameters";
import type { ScenarioChoice } from "../lib/presentation";

/** 실행한 뒤 폼 대신 보여 주는 한 줄 요약. 결과가 화면 위쪽으로 올라오게 한다. */
export function RunConditionSummary({
  scenarios,
  running,
  onEdit,
}: {
  scenarios: ScenarioChoice[];
  running: boolean;
  onEdit: () => void;
}) {
  const { control } = useFormContext<
    SimulatorFormValues,
    unknown,
    SimulatorDraft
  >();
  const [
    mode,
    scenarioKey,
    prompt,
    text,
    files,
    existingAssetIds,
    jsonSchema,
    temperature,
    maxTokens,
    reasoningEffort,
    comparisons,
  ] = useWatch({
    control,
    name: [
      "mode",
      "scenarioKey",
      "prompt",
      "text",
      "files",
      "existingAssetIds",
      "jsonSchema",
      "temperature",
      "maxTokens",
      "reasoningEffort",
      "comparisons",
    ],
  });
  const scenario = scenarios.find((item) => item.key === scenarioKey);
  const common = [
    temperature && `${PARAMETER_LABELS.temperature} ${temperature}`,
    maxTokens && `${PARAMETER_LABELS.maxTokens} ${maxTokens}`,
    reasoningEffort && `${PARAMETER_LABELS.reasoningEffort} ${reasoningEffort}`,
  ].filter(Boolean);
  return (
    <section
      aria-label="실행 조건"
      className="flex flex-wrap items-center gap-5 rounded-2xl bg-white px-6 py-4"
    >
      <div className="flex min-w-0 flex-1 basis-105 flex-col gap-1.5">
        <div className="flex items-center gap-2">
          <span className="text-caption font-semibold text-grey-600">
            실행 조건
          </span>
          <Badge tone="grey">
            {mode === "scenario"
              ? (scenario?.name ?? "기본 시나리오")
              : "직접 입력"}
          </Badge>
        </div>
        <p className="truncate text-body-sm">
          <span className="text-grey-600">Prompt</span>&nbsp; {prompt}
        </p>
        <p className="text-caption text-grey-600 tabular-nums">
          모델 {comparisons.length}개 ·{" "}
          {inputSummary({
            prompt,
            text,
            imageCount: files.length + existingAssetIds.length,
            jsonSchema,
          })}{" "}
          · 공통 설정 {common.length ? common.join(" · ") : "기본값"}
        </p>
      </div>
      <div className="ml-auto flex flex-col items-end gap-1.5">
        <Button
          size="sm"
          variant="secondary"
          disabled={running}
          onClick={onEdit}
        >
          조건 수정해 새 비교
        </Button>
        {running && (
          <span className="text-caption text-grey-600">
            실행이 끝나면 조건을 수정할 수 있어요
          </span>
        )}
      </div>
    </section>
  );
}
