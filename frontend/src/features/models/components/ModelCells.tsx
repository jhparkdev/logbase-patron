import { Badge } from "../../../shared/components/ui/Badge";
import { formatKstDateTime } from "../../../shared/lib/format";
import { formatPricePerMillion } from "../../../shared/lib/price";
import type { ModelRow } from "../api/models";
import { testResultView } from "../lib/view";

const NO_TEST_LABEL = "미실행";

const DOT_CLASS = { green: "bg-green-500", red: "bg-red-500" } as const;

/** 단가 없음은 0이 아닌 미확인. 있으면 100만 토큰당 단가로 변환 */
export function PriceCell({
  perToken,
}: {
  perToken: string | null | undefined;
}) {
  return perToken === null || perToken === undefined ? (
    <Badge tone="yellow">미확인</Badge>
  ) : (
    formatPricePerMillion(perToken)
  );
}

/** 색 점은 성공·실패 표시, 결과 글자는 화면 낭독기용 */
export function LastTestCell({
  row,
}: {
  row: Pick<ModelRow, "last_test_at" | "last_test_status">;
}) {
  if (row.last_test_at === null || row.last_test_status === null) {
    return <span className="text-grey-600">{NO_TEST_LABEL}</span>;
  }
  const result = testResultView(row.last_test_status);
  return (
    <span className="inline-flex items-center gap-2">
      <span
        aria-hidden="true"
        className={`size-2 rounded-full ${DOT_CLASS[result.dot]}`}
      />
      {formatKstDateTime(row.last_test_at)}
      <span className="sr-only">{result.label}</span>
    </span>
  );
}
