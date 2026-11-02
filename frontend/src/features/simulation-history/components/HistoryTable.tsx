import { Button } from "../../../shared/components/ui/Button";
import { formatCount } from "../../../shared/lib/format";
import type { HistoryRow } from "../lib/presentation";
import { changeHistorySort, type HistorySearch } from "../lib/search";
import {
  HistoryCost,
  HistoryCostStatus,
  HistoryStatus,
  HistoryTimestamp,
} from "./HistoryValues";

const columns = [
  ["requestedAt", "실행 시각", "w-28"],
  ["id", "Simulation ID", "w-36"],
  ["scenario", "시나리오", "w-30"],
  ["modelCount", "모델 수", "w-22"],
  ["status", "실행 상태", "w-26"],
  ["costStatus", "비용 상태", "w-40"],
  ["totalCost", "총 비용 (USD)", "w-32"],
] as const;
const cell = "h-20 border-b border-grey-100 px-3 py-3 text-body-sm";
export function HistoryTable({
  rows,
  search,
  onSearch,
}: {
  rows: readonly HistoryRow[];
  search: HistorySearch;
  onSearch: (search: HistorySearch) => void;
}) {
  const open = (key: string) =>
    onSearch({ ...search, selected: key, detail: true });
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[60rem] table-fixed">
        <caption className="sr-only">
          시뮬레이션 실행 이력. 정렬과 페이지 처리는 서버에서 수행해요.
        </caption>
        <colgroup>
          {columns.map(([key, , width]) => (
            <col key={key} className={width} />
          ))}
          <col className="w-26" />
        </colgroup>
        <thead className="bg-grey-50">
          <tr>
            {columns.map(([key, label]) => (
              <th
                scope="col"
                key={key}
                aria-sort={
                  key === "totalCost"
                    ? undefined
                    : search.sort === key
                      ? search.direction === "asc"
                        ? "ascending"
                        : "descending"
                      : "none"
                }
                className={`whitespace-nowrap px-3 py-3 text-label font-medium text-grey-600 ${key === "modelCount" || key === "totalCost" ? "text-right" : "text-left"}`}
              >
                {key === "totalCost" ? (
                  label
                ) : (
                  <button
                    type="button"
                    aria-label={`${label} 정렬`}
                    onClick={() => onSearch(changeHistorySort(search, key))}
                    className="inline-flex items-center gap-1 focus-visible:outline-2 focus-visible:outline-brand"
                  >
                    {label}
                    <span
                      aria-hidden="true"
                      className="inline-flex size-4 shrink-0 items-center justify-center"
                    >
                      {search.sort === key
                        ? search.direction === "asc"
                          ? "↑"
                          : "↓"
                        : "↕"}
                    </span>
                  </button>
                )}
              </th>
            ))}
            <th scope="col">
              <span className="sr-only">상세</span>
            </th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr
              key={row.key}
              className={
                search.selected === row.key ? "bg-blue-50" : "hover:bg-grey-50"
              }
            >
              <td className={`${cell} whitespace-nowrap tabular-nums`}>
                <HistoryTimestamp utc={row.requestedAt} />
              </td>
              <td className={cell}>
                <button
                  type="button"
                  onClick={() => open(row.key)}
                  title={row.key}
                  className="block w-full truncate text-left font-semibold text-blue-600 underline underline-offset-4 focus-visible:outline-2 focus-visible:outline-brand"
                >
                  {row.key}
                </button>
              </td>
              <td className={cell}>
                <span className="line-clamp-2" title={row.scenario}>
                  {row.scenario}
                </span>
              </td>
              <td className={`${cell} text-right tabular-nums`}>
                {formatCount(row.modelCount)}
              </td>
              <td className={cell}>
                <HistoryStatus status={row.status} />
              </td>
              <td className={cell}>
                <HistoryCostStatus cost={row.cost} />
              </td>
              <td className={`${cell} text-right`}>
                <HistoryCost cost={row.cost} />
              </td>
              <td className={cell}>
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => open(row.key)}
                  aria-label={`${row.key} 상세 보기`}
                >
                  상세 보기
                </Button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
