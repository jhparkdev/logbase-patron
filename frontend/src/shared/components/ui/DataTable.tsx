import type { ReactNode } from "react";
import dropDownIcon from "../../../assets/dropDown.svg";
import sortIcon from "../../../assets/sort.svg";
import type { SortState } from "../../lib/sort";
import { Icon } from "./Icon";

export type Column<T> = {
  key: string;
  header: ReactNode;
  /** 금액, 건수 같은 숫자는 오른쪽 정렬 */
  align?: "left" | "right";
  sortable?: boolean;
  render: (row: T) => ReactNode;
};

type DataTableProps<T> = {
  /** 화면 낭독기가 읽는 표 이름 */
  caption: string;
  columns: Column<T>[];
  rows: T[];
  rowKey: (row: T) => string;
  sort?: SortState;
  onSortChange?: (key: string) => void;
  /** 행이 없을 때 보여 줄 내용(결과 블록) */
  empty: ReactNode;
  /** 행 바탕처럼 행마다 달라지는 모양. 예: 실패한 호출을 연하게 물들임 */
  rowClassName?: (row: T) => string;
};

/** 정렬은 서버가 한다. 이 표는 정렬 상태를 보여 주고, 바꿀 칸만 알린다. */
export function DataTable<T>({
  caption,
  columns,
  rows,
  rowKey,
  sort,
  onSortChange,
  empty,
  rowClassName,
}: DataTableProps<T>) {
  return (
    // relative: 칸 안의 sr-only(absolute) 글자가 이 상자 밖 카드를 넓히지 않게 상자 안에 가둔다
    <div className="relative overflow-x-auto rounded-b-2xl">
      <table className="w-full min-w-max text-body-sm tabular-nums">
        <caption className="sr-only">{caption}</caption>
        <thead className="bg-grey-50 text-label text-grey-600">
          <tr>
            {columns.map((column) => {
              const direction =
                sort?.key === column.key ? sort.direction : undefined;
              return (
                <th
                  key={column.key}
                  scope="col"
                  aria-sort={
                    column.sortable ? ARIA_SORT[direction ?? "none"] : undefined
                  }
                  className={`px-4 py-2.5 font-medium whitespace-nowrap first:pl-6 last:pr-6 ${alignClass(column.align)}`}
                >
                  {column.sortable && onSortChange ? (
                    <button
                      type="button"
                      onClick={() => onSortChange(column.key)}
                      className={`inline-flex items-center gap-1 rounded-sm hover:text-grey-900 focus-visible:outline-2 focus-visible:outline-brand ${direction ? "text-grey-900" : ""}`}
                    >
                      {column.header}
                      <SortMark direction={direction} />
                    </button>
                  ) : (
                    column.header
                  )}
                </th>
              );
            })}
          </tr>
        </thead>
        <tbody>
          {rows.length === 0 ? (
            <tr>
              <td colSpan={columns.length}>{empty}</td>
            </tr>
          ) : (
            rows.map((row) => (
              <tr
                key={rowKey(row)}
                className={`border-t border-grey-100 hover:bg-grey-50 ${rowClassName?.(row) ?? ""}`}
              >
                {columns.map((column) => (
                  <td
                    key={column.key}
                    className={`h-12 px-4 first:pl-6 last:pr-6 ${alignClass(column.align)}`}
                  >
                    {column.render(row)}
                  </td>
                ))}
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}

const ARIA_SORT = {
  asc: "ascending",
  desc: "descending",
  none: "none",
} as const;

function alignClass(align: Column<unknown>["align"]) {
  return align === "right" ? "text-right" : "text-left";
}

/** 정렬 중인 칸은 방향 화살표, 아닌 칸은 위아래 화살표를 보여 준다. */
function SortMark({ direction }: { direction?: SortState["direction"] }) {
  if (!direction) {
    return <Icon src={sortIcon} className="h-2.5 w-1.5 text-grey-400" />;
  }
  return (
    <Icon
      src={dropDownIcon}
      className={`h-1.5 w-2.5 text-brand ${direction === "asc" ? "rotate-180" : ""}`}
    />
  );
}
