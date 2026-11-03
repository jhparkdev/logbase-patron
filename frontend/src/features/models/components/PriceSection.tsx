import type { ModelDetail } from "../api/models";
import { timeOrNone } from "../lib/view";
import { PriceCell } from "./ModelCells";

const PRICE_LABELS = { input: "Input 단가", output: "Output 단가" } as const;

/** 단가 카드 두 장. 가격이 없으면 0이 아니라 미확인 */
export function PriceSection({ model }: { model: ModelDetail }) {
  const price = model.current_price;
  const cards = [
    { label: PRICE_LABELS.input, perToken: price?.input_price_per_token },
    { label: PRICE_LABELS.output, perToken: price?.output_price_per_token },
  ];
  return (
    <div className="grid grid-cols-2 gap-3">
      {cards.map((card) => (
        <div
          key={card.label}
          className="flex flex-col gap-1 rounded-2xl bg-blue-50 p-4"
        >
          <span className="text-label font-medium text-grey-700">
            {card.label}
          </span>
          <span className="text-title font-bold tabular-nums">
            <PriceCell perToken={card.perToken} />
            {card.perToken != null && (
              <span className="ml-1 text-label font-semibold text-grey-600">
                USD
              </span>
            )}
          </span>
        </div>
      ))}
    </div>
  );
}

/** 구역 제목 오른쪽에 붙는 가격 확인 시각 */
export function priceCheckedCaption(model: ModelDetail): string {
  return `최종 확인 ${timeOrNone(model.current_price?.checked_at ?? null)}`;
}
