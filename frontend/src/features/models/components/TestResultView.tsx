import { Badge } from "../../../shared/components/ui/Badge";
import { CostAmount } from "../../../shared/components/ui/CostAmount";
import { formatCount, formatKstDateTime } from "../../../shared/lib/format";
import type { ConnectionTestResult } from "../api/models";
import { testCostView, testResultView } from "../lib/view";
import { Row, Rows } from "./DetailRows";

// 호출이 실패하면 응답 시간·토큰·업체를 알 수 없음
const UNKNOWN_LABEL = "미확인";

const countOrUnknown = (count: number | null) =>
  count === null ? UNKNOWN_LABEL : formatCount(count);

/** 연결 테스트 결과. 비용은 확정·추정·미확인을 구분하고 모르면 0이 아니라 미확인 */
export function TestResultView({ result }: { result: ConnectionTestResult }) {
  const outcome = testResultView(result.status);
  return (
    <Rows>
      <Row label="결과">
        <Badge tone={outcome.dot}>{outcome.label}</Badge>
      </Row>
      <Row label="테스트 시각">{formatKstDateTime(result.tested_at)}</Row>
      <Row label="응답 시간">
        {result.latency_ms === null
          ? UNKNOWN_LABEL
          : `${formatCount(result.latency_ms)} ms`}
      </Row>
      <Row label="입력 토큰">{countOrUnknown(result.input_tokens)}</Row>
      <Row label="출력 토큰">{countOrUnknown(result.output_tokens)}</Row>
      <Row label="비용 (USD)">
        <CostAmount cost={testCostView(result)} precision="perCall" />
      </Row>
      <Row label="호출 업체">{result.actual_provider ?? UNKNOWN_LABEL}</Row>
      {result.error_message !== null && (
        <Row label="오류 내용">{result.error_message}</Row>
      )}
    </Rows>
  );
}
