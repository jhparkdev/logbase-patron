import type { components } from "../../../shared/api/schema";
import { formatCount } from "../../../shared/lib/format";

type Detail = Pick<
  components["schemas"]["ProjectUsageDetail"],
  "task_count" | "call_count" | "unknown_cost_count"
>;

const TILE_CLASS = {
  plain: { box: "border border-grey-100", value: "" },
  warning: { box: "bg-warning-weak", value: "text-yellow-900" },
} as const;

/** 작업·호출 수와 비용 미확인 건수. 미확인이 있으면 눈에 띄게 둔다 */
export function ProjectCountTiles({ detail }: { detail: Detail }) {
  const tiles = [
    {
      label: "작업",
      value: `${formatCount(detail.task_count)}건`,
      tone: "plain",
    },
    {
      label: "API 호출",
      value: `${formatCount(detail.call_count)}회`,
      tone: "plain",
    },
    {
      label: "비용 미확인",
      value: `${formatCount(detail.unknown_cost_count)}건 미반영`,
      tone: detail.unknown_cost_count > 0 ? "warning" : "plain",
    },
  ] as const;
  return (
    <div className="grid grid-cols-3 gap-2">
      {tiles.map((tile) => (
        <div
          key={tile.label}
          className={`flex flex-col gap-1 rounded-xl p-3 ${TILE_CLASS[tile.tone].box}`}
        >
          <span className="text-caption text-grey-600">{tile.label}</span>
          <span
            className={`font-bold tabular-nums ${TILE_CLASS[tile.tone].value}`}
          >
            {tile.value}
          </span>
        </div>
      ))}
    </div>
  );
}
