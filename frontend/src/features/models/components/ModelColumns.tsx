import { Badge } from "../../../shared/components/ui/Badge";
import { Button } from "../../../shared/components/ui/Button";
import type { Column } from "../../../shared/components/ui/DataTable";
import { TextLink } from "../../../shared/components/ui/TextLink";
import type { ModelRow } from "../api/models";
import { modalitiesLabel, statusBadge } from "../lib/view";
import { LastTestCell, PriceCell } from "./ModelCells";

const PRICE_UNIT = <span className="font-normal text-grey-500">(USD/1M)</span>;

// key는 API 정렬 값과 동일. 머리글 클릭 시 주소의 sort로 저장. 테스트 버튼은 누른 행을 onTest로 넘김
export function modelColumns(
  onTest: (row: ModelRow) => void,
): Column<ModelRow>[] {
  return [
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
      render: (row) => modalitiesLabel(row.input_modalities),
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
      render: (row) => (
        <Button
          variant="secondary"
          size="sm"
          aria-label={`${row.display_name} 연결 테스트`}
          onClick={() => onTest(row)}
        >
          테스트
        </Button>
      ),
    },
  ];
}
