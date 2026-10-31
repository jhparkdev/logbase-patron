import { useId } from "react";
import { Button } from "../../../shared/components/ui/Button";
import type { ModelFavoritesView } from "../lib/favorites";
import type { ModelChoice } from "../lib/presentation";

export function ModelFavoriteButton({
  choice,
  favorites,
}: {
  choice: ModelChoice;
  favorites: ModelFavoritesView;
}) {
  const errorId = useId();
  const ready = favorites.kind === "ready";
  const selected = ready && favorites.keys.includes(choice.key);
  const saving = ready && !!favorites.savingKeys?.includes(choice.key);
  const failed = ready && !!favorites.failedKeys?.includes(choice.key);
  return (
    <>
      <Button
        size="sm"
        variant="secondary"
        className="size-8"
        aria-label={`${choice.name} · ${choice.provider} 즐겨찾기`}
        aria-pressed={selected}
        aria-busy={saving}
        aria-describedby={failed ? errorId : undefined}
        title={
          saving
            ? "즐겨찾기 변경 중"
            : ready
              ? selected
                ? "즐겨찾기 해제"
                : "즐겨찾기 등록"
              : "즐겨찾기를 불러온 뒤 사용할 수 있습니다"
        }
        disabled={!ready || saving}
        onClick={() => {
          if (favorites.kind === "ready" && !saving)
            favorites.onSet(choice.key, !selected);
        }}
      >
        <span
          aria-hidden="true"
          className={
            selected
              ? "text-section text-yellow-900"
              : "text-section text-grey-600"
          }
        >
          {selected ? "★" : "☆"}
        </span>
      </Button>
      {failed && (
        <p id={errorId} role="alert" className="mt-1 text-caption text-red-600">
          즐겨찾기를 변경하지 못했습니다. 다시 누르시기 바랍니다.
        </p>
      )}
    </>
  );
}
