import { selectedComparisonCount } from "../lib/comparisons";
import type { ModelFavoritesView } from "../lib/favorites";
import { MODEL_LIMITS } from "../lib/limits";
import type { ModelChoice } from "../lib/presentation";
import { ModelCreatorBadge } from "./ModelCreatorBadge";
import { ModelFavoriteButton } from "./ModelFavoriteButton";

export function ModelCatalogTable({
  choices,
  pending,
  unavailable,
  favorites,
  onToggle,
  counts,
}: {
  choices: ModelChoice[];
  pending: string[];
  unavailable: boolean;
  favorites: ModelFavoritesView;
  onToggle: (key: string) => void;
  counts?: Readonly<Record<string, number>>;
}) {
  return (
    <div className="max-h-64 overflow-y-auto rounded-control border border-grey-200">
      <table className="w-full text-left text-body-sm">
        <caption className="sr-only">비교할 모델 카탈로그</caption>
        <thead className="sticky top-0 bg-grey-50 text-label text-grey-600">
          <tr>
            <th scope="col" className="p-3">
              선택
            </th>
            <th scope="col" className="p-3">
              모델
            </th>
            <th scope="col" className="p-3">
              Provider
            </th>
            <th scope="col" className="p-3">
              입력 지원
            </th>
            <th scope="col" className="p-3">
              즐겨찾기
            </th>
          </tr>
        </thead>
        <tbody>
          {choices.map((choice) => {
            const checked = pending.includes(choice.key);
            return (
              <tr
                key={choice.key}
                className="border-t border-grey-100 hover:bg-grey-50"
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
                  {choice.name}
                  <div className="mt-1">
                    <ModelCreatorBadge creator={choice.creator} />
                  </div>
                  {!choice.selectable && (
                    <p className="mt-1 text-caption font-normal text-grey-600">
                      {choice.unavailableReason ?? "선택 불가"}
                    </p>
                  )}
                </th>
                <td className="p-3 text-grey-700">{choice.provider}</td>
                <td className="p-3 text-grey-600">
                  {choice.supportsImages ? "텍스트·이미지" : "텍스트"}
                </td>
                <td className="p-3">
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
