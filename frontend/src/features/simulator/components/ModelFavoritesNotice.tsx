import { Button } from "../../../shared/components/ui/Button";
import { Result } from "../../../shared/components/ui/Result";
import { Skeleton } from "../../../shared/components/ui/Skeleton";
import type { ModelFavoritesView } from "../lib/favorites";

export function ModelFavoritesNotice({
  favorites,
}: {
  favorites: ModelFavoritesView;
}) {
  if (favorites.kind === "loading")
    return (
      <div className="py-4">
        <p role="status" className="mb-3 text-body-sm text-grey-600">
          즐겨찾기를 불러오고 있어요
        </p>
        <Skeleton className="h-24 w-full" />
      </div>
    );
  if (favorites.kind === "error")
    return (
      <Result
        title="즐겨찾기를 불러오지 못했어요"
        description="잠시 후 다시 시도해 주세요."
        action={
          favorites.onRetry && (
            <Button variant="secondary" onClick={favorites.onRetry}>
              다시 시도
            </Button>
          )
        }
      />
    );
  if (favorites.kind === "unavailable")
    return (
      <Result
        title="즐겨찾기를 준비하고 있어요"
        description="전체 모델에서 비교할 모델을 선택해 주세요."
      />
    );
  return null;
}
