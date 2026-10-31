import { Button } from "../../../shared/components/ui/Button";
import { MODEL_LIMITS } from "../lib/limits";
import type { ModelChoice } from "../lib/presentation";
import { ComparisonSettings } from "./ComparisonSettings";
import { ModelCreatorBadge } from "./ModelCreatorBadge";

export function ModelComparisonCard({
  index,
  choice,
  count,
  onRemove,
  onDuplicate,
}: {
  index: number;
  choice?: ModelChoice;
  count: number;
  onRemove: () => void;
  onDuplicate: () => void;
}) {
  return (
    <li className="rounded-control border border-grey-200 p-3">
      <div className="mb-2 flex items-center justify-between gap-2">
        <h4 className="text-label font-semibold">비교 모델 {index + 1}</h4>
        <Button
          size="sm"
          variant="secondary"
          aria-label={`비교 모델 ${index + 1} 제거`}
          disabled={count === 1}
          onClick={onRemove}
        >
          제거
        </Button>
      </div>
      <p className="text-body-sm font-semibold">
        {choice?.name ?? "모델 선택 필요"}
      </p>
      <div className="mt-2">
        <ModelCreatorBadge creator={choice?.creator} />
      </div>
      {choice && (
        <div className="mt-1 flex items-center gap-2 text-caption text-grey-600">
          <span>{choice.provider}</span>
          <span>· {choice.supportsImages ? "텍스트·이미지" : "텍스트"}</span>
        </div>
      )}
      {choice && !choice.selectable && (
        <p className="mt-1 text-caption text-red-600">
          {choice.unavailableReason ?? "선택 불가"}
        </p>
      )}
      <ComparisonSettings index={index} choice={choice} />
      <Button
        size="sm"
        variant="secondary"
        className="mt-3"
        aria-label={`비교 모델 ${index + 1} 다른 설정으로 비교`}
        disabled={
          count >= MODEL_LIMITS.max ||
          !choice?.selectable ||
          !choice.tuningParameters?.length
        }
        onClick={onDuplicate}
      >
        다른 설정으로 비교
      </Button>
    </li>
  );
}
