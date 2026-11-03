import { CostAmount } from "../../../shared/components/ui/CostAmount";
import type { ConnectionTestResult } from "../api/models";
import { testStatCells } from "../lib/testStats";

/** 이번에 실행한 연결 테스트의 숫자 네 칸. 규격은 docs/design/tokens.md "상세 패널 숫자 칸" */
export function TestStatCells({
  result,
}: {
  result: ConnectionTestResult | undefined;
}) {
  return (
    <dl className="grid grid-cols-4 gap-2">
      {testStatCells(result).map((cell) => (
        <div
          key={cell.label}
          className="flex flex-col gap-1 rounded-xl bg-white p-3"
        >
          <dt className="whitespace-nowrap text-caption text-grey-600">
            {cell.label}
          </dt>
          <dd className="font-bold tabular-nums">
            {"cost" in cell ? (
              <CostAmount cost={cell.cost} precision="perCall" />
            ) : (
              <>
                {cell.value}
                {cell.unit && (
                  <span className="ml-0.5 text-caption font-medium text-grey-600">
                    {cell.unit}
                  </span>
                )}
              </>
            )}
          </dd>
        </div>
      ))}
    </dl>
  );
}
