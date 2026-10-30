import { formatCount } from "../../../shared/lib/format";
import type { ResultSort, SlotView } from "../lib/presentation";
import { CostValue, durationLabel, ExecutionStatus } from "./ResultValues";

const columns = [
  { key: "model", label: "모델·Provider" },
  { key: "duration", label: "응답 시간" },
  { key: "inputTokens", label: "입력 토큰" },
  { key: "outputTokens", label: "출력 토큰" },
  { key: "cost", label: "비용 (USD)" },
] as const;
export function ResultTable({
  slots,
  sort,
  onSort,
}: {
  slots: SlotView[];
  sort?: ResultSort;
  onSort?: (value: ResultSort) => void;
}) {
  return (
    <div className="overflow-x-auto rounded-2xl bg-white">
      <table className="w-full text-body-sm">
        <caption className="sr-only">
          모델별 실행 상태·비용·출력 검증 비교
        </caption>
        <thead className="bg-grey-50 text-label text-grey-600">
          <tr>
            {columns.map(({ key, label }, index) => (
              <th
                key={key}
                scope="col"
                aria-sort={
                  sort?.key === key
                    ? sort.direction === "asc"
                      ? "ascending"
                      : "descending"
                    : undefined
                }
                className={`whitespace-nowrap px-4 py-3 ${index === 0 ? "text-left" : "text-right"}`}
              >
                {onSort ? (
                  <button
                    type="button"
                    onClick={() =>
                      onSort({
                        key,
                        direction:
                          sort?.key === key && sort.direction === "asc"
                            ? "desc"
                            : "asc",
                      })
                    }
                    className="rounded-lg focus-visible:outline-2 focus-visible:outline-brand"
                  >
                    {label}{" "}
                    <span aria-hidden="true">
                      {sort?.key === key
                        ? sort.direction === "asc"
                          ? "↑"
                          : "↓"
                        : "↕"}
                    </span>
                  </button>
                ) : (
                  label
                )}
              </th>
            ))}
            <th scope="col" className="px-4 py-3 text-left">
              실행 상태
            </th>
            <th scope="col" className="px-4 py-3 text-left">
              JSON 검증
            </th>
            <th scope="col" className="px-4 py-3 text-left">
              Schema 검증
            </th>
          </tr>
        </thead>
        <tbody>
          {slots.map((slot) => (
            <tr
              key={slot.key}
              className="border-t border-grey-100 hover:bg-grey-50"
            >
              <th
                scope="row"
                className="max-w-56 break-words px-4 py-4 text-left font-semibold"
              >
                {slot.name}
                <span className="mt-1 block text-caption font-normal text-grey-600">
                  {slot.provider}
                </span>
              </th>
              <td className="px-4 py-4 text-right tabular-nums">
                {durationLabel(slot.durationMs)}
              </td>
              <td className="px-4 py-4 text-right tabular-nums">
                {slot.inputTokens === null
                  ? "미수신"
                  : formatCount(slot.inputTokens)}
              </td>
              <td className="px-4 py-4 text-right tabular-nums">
                {slot.outputTokens === null
                  ? "미수신"
                  : formatCount(slot.outputTokens)}
              </td>
              <td className="px-4 py-4 text-right">
                <CostValue cost={slot.cost} />
              </td>
              <td className="px-4 py-4">
                <ExecutionStatus status={slot.status} />
              </td>
              <td className="px-4 py-4">{slot.jsonValidation}</td>
              <td className="px-4 py-4">{slot.schemaValidation}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
