import { Badge } from "../../../shared/components/ui/Badge";
import { Button } from "../../../shared/components/ui/Button";
import {
  cardWarnings,
  type ResolvedSetting,
  resolvedSettings,
  unitPriceLabel,
} from "../lib/card-view";
import type { ComparisonValues } from "../lib/comparisons";
import { MODEL_LIMITS } from "../lib/limits";
import type { ParameterKey } from "../lib/parameters";
import type { ModelChoice, ScenarioChoice } from "../lib/presentation";
import { ComparisonSettings } from "./ComparisonSettings";
import { ModelCreatorBadge } from "./ModelCreatorBadge";
import { SupportTags } from "./SupportTags";

const VALUE_CLASS: Record<ResolvedSetting["source"], string> = {
  custom: "font-semibold text-blue-600",
  common: "",
  scenario: "",
  default: "text-grey-600",
  unsupported: "text-grey-500",
};

export function ModelComparisonCard({
  index,
  choice,
  comparison,
  common,
  scenario,
  hasImages,
  hasSchema,
  count,
  onRemove,
  onDuplicate,
}: {
  index: number;
  choice?: ModelChoice;
  comparison: ComparisonValues;
  common: Record<ParameterKey, string>;
  scenario?: ScenarioChoice;
  hasImages: boolean;
  hasSchema: boolean;
  count: number;
  onRemove: () => void;
  onDuplicate: () => void;
}) {
  const number = index + 1;
  const warnings = cardWarnings(choice, { hasImages, hasSchema });
  const settings = resolvedSettings(
    comparison,
    common,
    scenario?.defaults,
    choice,
  );
  const custom = comparison.settings.mode === "custom";
  const price = unitPriceLabel(choice?.price);
  return (
    <li
      className={`flex min-w-0 flex-col gap-2.5 rounded-xl border bg-white p-3.5 ${warnings.length ? "border-red-500" : "border-grey-200"}`}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <h4 className="text-body-sm font-semibold">
            <span className="sr-only">비교 모델 {number} · </span>
            {choice?.name ?? "모델 선택 필요"}
          </h4>
          <div className="mt-1 flex flex-wrap items-center gap-1.5 text-caption text-grey-600">
            <ModelCreatorBadge creator={choice?.creator} />
            {choice && <span>{choice.provider}</span>}
          </div>
        </div>
        <Badge tone={custom ? "blue" : "grey"}>
          {custom ? "개별" : "공통"}
        </Badge>
      </div>
      {choice && (
        <SupportTags
          choice={choice}
          hasImages={hasImages}
          hasSchema={hasSchema}
        />
      )}
      {warnings.map((warning) => (
        <p key={warning} className="text-caption text-red-600">
          {warning}
        </p>
      ))}
      <dl className="flex flex-col gap-1 border-t border-grey-100 pt-2.5 text-caption">
        {settings.map((setting) => (
          <div key={setting.key} className="flex justify-between gap-2">
            <dt className="text-grey-600">{setting.label}</dt>
            <dd className={`tabular-nums ${VALUE_CLASS[setting.source]}`}>
              {setting.value}
            </dd>
          </div>
        ))}
        <div className="mt-1 flex items-center justify-between gap-2">
          <dt className="text-grey-600">단가 USD/1M</dt>
          <dd className="tabular-nums">
            {price ?? <Badge tone="yellow">미확인</Badge>}
          </dd>
        </div>
      </dl>
      <ComparisonSettings index={index} choice={choice} />
      <div className="mt-auto flex items-center gap-1.5 pt-1">
        <Button
          size="sm"
          variant="secondary"
          title="같은 모델을 다른 설정으로 한 번 더 비교해요"
          aria-label={`비교 모델 ${number} 다른 설정으로 비교`}
          disabled={
            count >= MODEL_LIMITS.max ||
            !choice?.selectable ||
            !choice.tuningParameters?.length
          }
          onClick={onDuplicate}
        >
          복제
        </Button>
        <Button
          size="sm"
          variant="secondary"
          className="ml-auto"
          aria-label={`비교 모델 ${number} 제거`}
          disabled={count === 1}
          onClick={onRemove}
        >
          제거
        </Button>
      </div>
    </li>
  );
}
