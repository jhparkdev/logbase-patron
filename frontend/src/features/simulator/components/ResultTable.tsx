import { Badge } from "../../../shared/components/ui/Badge";
import { formatCount } from "../../../shared/lib/format";
import type { ResultSort, SlotView } from "../lib/presentation";
import { CostValue, durationLabel, ExecutionStatus } from "./ResultValues";

const columns = [
  { key: "duration", label: "응답 시간" },
  { key: "inputTokens", label: "입력 토큰" },
  { key: "outputTokens", label: "출력 토큰" },
  { key: "cost", label: "비용 (USD)" },
] as const;

/** 실패·시간 초과 행은 P-01 호출 내역처럼 바탕을 연하게 물들인다 */
const ROW_CLASS: Record<SlotView["status"]["tone"], string> = {
  green: "",
  grey: "",
  yellow: "bg-yellow-50/60",
  red: "bg-red-50/60",
};
const VALIDATION_TONE: Record<string, "green" | "red" | "grey"> = {
  성공: "green",
  실패: "red",
};

function BestMark({ label }: { label: string }) {
  return (
    <span className="mr-1.5 inline-flex h-5 items-center rounded-full bg-brand-weak px-1.5 text-caption font-bold text-blue-600">
      {label}
    </span>
  );
}

export function ResultTable({
  slots,
  sort,
  onSort,
  best = { fastest: [], cheapest: [] },
}: {
  slots: SlotView[];
  sort?: ResultSort;
  onSort?: (value: ResultSort) => void;
  best?: { fastest: readonly string[]; cheapest: readonly string[] };
}) {
  const sortableHeader = (key: ResultSort["key"], label: string) =>
    onSort ? (
      <button
        type="button"
        onClick={() =>
          onSort({
            key,
            direction:
              sort?.key === key && sort.direction === "asc" ? "desc" : "asc",
          })
        }
        className="rounded-lg focus-visible:outline-2 focus-visible:outline-brand"
      >
        {label}{" "}
        <span aria-hidden="true">
          {sort?.key === key ? (sort.direction === "asc" ? "↑" : "↓") : "↕"}
        </span>
      </button>
    ) : (
      label
    );
  const ariaSort = (key: ResultSort["key"]) =>
    sort?.key === key
      ? sort.direction === "asc"
        ? "ascending"
        : "descending"
      : undefined;
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-body-sm">
        <caption className="sr-only">
          모델별 실행 상태·비용·출력 검증 비교
        </caption>
        <thead className="bg-grey-50 text-label text-grey-600">
          <tr>
            <th
              scope="col"
              aria-sort={ariaSort("model")}
              className="px-4 py-3 pl-6 text-left whitespace-nowrap"
            >
              {sortableHeader("model", "모델 · Provider")}
            </th>
            <th scope="col" className="px-4 py-3 text-left">
              실행 상태
            </th>
            {columns.map(({ key, label }) => (
              <th
                key={key}
                scope="col"
                aria-sort={ariaSort(key)}
                className="px-4 py-3 text-right whitespace-nowrap"
              >
                {sortableHeader(key, label)}
              </th>
            ))}
            <th scope="col" className="px-4 py-3 text-left">
              JSON 검증
            </th>
            <th scope="col" className="px-4 py-3 pr-6 text-left">
              Schema 검증
            </th>
          </tr>
        </thead>
        <tbody>
          {slots.map((slot) => (
            <tr
              key={slot.key}
              className={`border-t border-grey-100 hover:bg-grey-50 ${ROW_CLASS[slot.status.tone]}`}
            >
              <th
                scope="row"
                className="max-w-56 px-4 py-4 pl-6 text-left font-semibold"
              >
                {slot.name}
                <span className="mt-1 block text-caption font-normal text-grey-600">
                  {slot.provider}
                </span>
              </th>
              <td className="px-4 py-4">
                <ExecutionStatus status={slot.status} />
              </td>
              <td className="px-4 py-4 text-right tabular-nums whitespace-nowrap">
                {best.fastest.includes(slot.key) && <BestMark label="최단" />}
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
              <td className="px-4 py-4 text-right whitespace-nowrap">
                {best.cheapest.includes(slot.key) && <BestMark label="최저" />}
                <CostValue cost={slot.cost} />
              </td>
              <td className="px-4 py-4">
                <Badge tone={VALIDATION_TONE[slot.jsonValidation] ?? "grey"}>
                  {slot.jsonValidation}
                </Badge>
              </td>
              <td className="px-4 py-4 pr-6">
                <Badge tone={VALIDATION_TONE[slot.schemaValidation] ?? "grey"}>
                  {slot.schemaValidation}
                </Badge>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
