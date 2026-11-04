import { Badge } from "../../../shared/components/ui/Badge";
import { unitPriceLabel } from "../lib/card-view";
import { selectedComparisonCount } from "../lib/comparisons";
import type { ModelFavoritesView } from "../lib/favorites";
import { MODEL_LIMITS } from "../lib/limits";
import type { ModelChoice } from "../lib/presentation";
import { ModelCreatorBadge } from "./ModelCreatorBadge";
import { ModelFavoriteButton } from "./ModelFavoriteButton";
import { SupportTags } from "./SupportTags";

export function ModelCatalogTable({
  choices,
  pending,
  unavailable,
  favorites,
  onToggle,
  counts,
  showSchema = true,
}: {
  choices: ModelChoice[];
  pending: string[];
  unavailable: boolean;
  favorites: ModelFavoritesView;
  onToggle: (key: string) => void;
  counts?: Readonly<Record<string, number>>;
  showSchema?: boolean;
}) {
  return (
    <div className="max-h-80 overflow-y-auto rounded-control border border-grey-200">
      <table className="w-full text-left text-body-sm">
        <caption className="sr-only">비교할 모델 카탈로그</caption>
        <thead className="sticky top-0 bg-grey-50 text-label text-grey-600">
          <tr>
            <th scope="col" className="p-3">
              <span className="sr-only">선택</span>
            </th>
            <th scope="col" className="p-3">
              모델
            </th>
            <th scope="col" className="p-3">
              Provider
            </th>
            <th scope="col" className="p-3">
              지원
            </th>
            <th scope="col" className="p-3 text-right whitespace-nowrap">
              단가 USD/1M{" "}
              <span className="font-normal text-grey-500">입력 · 출력</span>
            </th>
            <th scope="col" className="p-3 text-center">
              즐겨찾기
            </th>
          </tr>
        </thead>
        <tbody>
          {choices.map((choice) => {
            const checked = pending.includes(choice.key);
            const price = unitPriceLabel(choice.price);
            return (
              <tr
                key={choice.key}
                className={`border-t border-grey-100 ${checked ? "bg-blue-50/60" : "hover:bg-grey-50"} ${choice.selectable ? "" : "text-grey-500"}`}
              >
                <td className="p-3">
                  <input
                    type="checkbox"
                    aria-label={`${choice.name} · ${choice.provider}`}
                    checked={checked}
                    disabled={
                      unavailable ||
                      (!checked &&
                        (!choice.selectable ||
                          selectedComparisonCount(
                            [...pending, choice.key],
                            counts,
                          ) > MODEL_LIMITS.max))
                    }
                    onChange={() => onToggle(choice.key)}
                    className="size-4 accent-brand focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand"
                  />
                </td>
                <th scope="row" className="p-3 font-semibold">
                  <span className="flex flex-wrap items-center gap-1.5">
                    {choice.name}
                    <ModelCreatorBadge creator={choice.creator} />
                  </span>
                  {!choice.selectable && (
                    <p className="mt-1 text-caption font-normal text-yellow-900">
                      {choice.unavailableReason ?? "지금은 고를 수 없어요"}
                    </p>
                  )}
                </th>
                <td className="p-3 text-grey-700">{choice.provider}</td>
                <td className="p-3">
                  <SupportTags choice={choice} showSchema={showSchema} />
                </td>
                <td className="p-3 text-right tabular-nums">
                  {price ?? <Badge tone="yellow">미확인</Badge>}
                </td>
                <td className="p-3 text-center">
                  <ModelFavoriteButton choice={choice} favorites={favorites} />
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
