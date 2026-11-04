import { Badge } from "../../../shared/components/ui/Badge";
import { formatCount } from "../../../shared/lib/format";
import { formatPricePerMillion } from "../../../shared/lib/price";
import type { OpenRouterModel } from "../api/models";
import { modalitiesFlow, releasedLabel } from "../lib/view";

const UNKNOWN_LABEL = "미확인";

type OpenRouterResultProps = {
  model: OpenRouterModel;
  selected: boolean;
  onSelect: (model: OpenRouterModel) => void;
};

/** OpenRouter 검색 결과 한 줄. 이미 등록된 모델은 고를 수 없음 */
export function OpenRouterResult({
  model,
  selected,
  onSelect,
}: OpenRouterResultProps) {
  const inputPrice = model.input_price_per_token;
  const outputPrice = model.output_price_per_token;
  const released = releasedLabel(model.created_at);
  return (
    <label
      className={`flex gap-3 rounded-xl border p-3 ${
        model.registered
          ? "border-grey-100 bg-grey-50 text-grey-500"
          : selected
            ? "cursor-pointer border-brand bg-brand-weak"
            : "cursor-pointer border-grey-100 hover:bg-grey-50"
      }`}
    >
      <input
        type="radio"
        name="openrouter-model"
        className="mt-1"
        checked={selected}
        disabled={model.registered}
        onChange={() => onSelect(model)}
      />
      <div className="flex min-w-0 flex-1 flex-col gap-1">
        <div className="flex items-baseline gap-2">
          <span className="font-bold">{model.name}</span>
          <span className="text-label break-all">
            {model.openrouter_model_id}
          </span>
          <span className="ml-auto flex shrink-0 items-center gap-2 text-label">
            {released && <span className="tabular-nums">{released}</span>}
            {model.provider}
            {model.registered && <Badge tone="grey">이미 등록됨</Badge>}
          </span>
        </div>
        <div className="flex flex-wrap gap-1">
          <Badge tone="grey">
            {modalitiesFlow(model.input_modalities, model.output_modalities)}
          </Badge>
          {model.supports_json_schema && <Badge tone="grey">JSON</Badge>}
          {model.supports_tools && <Badge tone="grey">함수 호출</Badge>}
        </div>
        <p className="flex flex-wrap items-center gap-x-1.5 text-label tabular-nums">
          Context{" "}
          {model.context_length === null
            ? UNKNOWN_LABEL
            : `${formatCount(model.context_length)} 토큰`}{" "}
          ·{" "}
          {inputPrice === null || outputPrice === null ? (
            <Badge tone="yellow">가격 미확인</Badge>
          ) : (
            `입력 ${formatPricePerMillion(inputPrice)} · 출력 ${formatPricePerMillion(outputPrice)} USD/1M`
          )}
        </p>
      </div>
    </label>
  );
}
