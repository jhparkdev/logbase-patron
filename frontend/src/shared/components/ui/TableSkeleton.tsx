import { Skeleton } from "./Skeleton";

/**
 * 표를 불러오는 동안의 모양. 머리글 줄(40px)과 행(48px) 높이를 DataTable과 맞춘다.
 * 칸 이름은 표를 그릴 때 함께 보여 준다.
 */
export function TableSkeleton({ rows }: { rows: number }) {
  const rowKeys = Array.from({ length: rows }, (_, index) => index);
  return (
    <div aria-hidden="true">
      <div className="h-10 bg-grey-50" />
      {rowKeys.map((key) => (
        <div
          key={key}
          className="flex h-12 items-center border-t border-grey-100 px-6"
        >
          <Skeleton className="h-4 flex-1" />
        </div>
      ))}
    </div>
  );
}
