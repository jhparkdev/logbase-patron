import { Badge } from "../../../shared/components/ui/Badge";
import type { Column } from "../../../shared/components/ui/DataTable";
import { TextLink } from "../../../shared/components/ui/TextLink";
import { formatKstDateTime } from "../../../shared/lib/format";
import type { ModelRow } from "../api/models";
import { formatPricePerMillion } from "../lib/price";
import { modalityLabel, statusBadge, testResultView } from "../lib/view";

const NO_TEST_LABEL = "미실행";
const PRICE_UNIT = <span className="font-normal text-grey-500">(USD/1M)</span>;

const DOT_CLASS = { green: "bg-green-500", red: "bg-red-500" } as const;

/** 단가 없음은 0이 아닌 미확인. 있으면 100만 토큰당 단가로 변환 */
function PriceCell({ perToken }: { perToken: string | null | undefined }) {
  return perToken === null || perToken === undefined ? (
    <Badge tone="yellow">미확인</Badge>
  ) : (
    formatPricePerMillion(perToken)
  );
}

/** 색 점은 성공·실패 표시, 결과 글자는 화면 낭독기용 */
function LastTestCell({ row }: { row: ModelRow }) {
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

// key는 API 정렬 값과 동일. 머리글 클릭 시 주소의 sort로 저장
export const COLUMNS: Column<ModelRow>[] = [
  {
    key: "display_name",
    header: "표시 이름",
    sortable: true,
    render: (row) => (
      <TextLink
        from="/models"
        to="/models"
        search={(prev) => ({ ...prev, model: row.model_id })}
      >
        {row.display_name}
      </TextLink>
    ),
  },
  {
    key: "openrouter_model_id",
    header: "Model ID",
    sortable: true,
    render: (row) => row.openrouter_model_id,
  },
  {
    key: "provider",
    header: "Provider",
    sortable: true,
    render: (row) => row.provider,
  },
  {
    key: "input_modalities",
    header: "지원 기능",
    sortable: true,
    render: (row) => row.input_modalities.map(modalityLabel).join(", "),
  },
  {
    key: "price_input",
    header: <>Input 가격 {PRICE_UNIT}</>,
    align: "right",
    sortable: true,
    render: (row) => (
      <PriceCell perToken={row.current_price?.input_price_per_token} />
    ),
  },
  {
    key: "price_output",
    header: <>Output 가격 {PRICE_UNIT}</>,
    align: "right",
    sortable: true,
    render: (row) => (
      <PriceCell perToken={row.current_price?.output_price_per_token} />
    ),
  },
  {
    key: "status",
    header: "상태",
    sortable: true,
    render: (row) => {
      const badge = statusBadge(row.status);
      return <Badge tone={badge.tone}>{badge.label}</Badge>;
    },
  },
  {
    key: "last_test_at",
    header: "마지막 테스트",
    sortable: true,
    render: (row) => <LastTestCell row={row} />,
  },
  {
    key: "test",
    header: <span className="sr-only">연결 테스트</span>,
    render: () => null,
  },
];
