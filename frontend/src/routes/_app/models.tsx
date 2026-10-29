import { createFileRoute } from "@tanstack/react-router";
import { z } from "zod";
import plusIcon from "../../assets/plus.svg";
import { Button } from "../../shared/components/ui/Button";
import { type Column, DataTable } from "../../shared/components/ui/DataTable";
import { PageHeader } from "../../shared/components/ui/PageHeader";
import { Pagination } from "../../shared/components/ui/Pagination";
import { Result } from "../../shared/components/ui/Result";
import { SearchField } from "../../shared/components/ui/SearchField";
import { SectionCard } from "../../shared/components/ui/SectionCard";
import { Select } from "../../shared/components/ui/Select";
import { PAGE_SIZE } from "../../shared/lib/pagination";
import { nextSort } from "../../shared/lib/sort";

const SORT_KEYS = [
  "name",
  "modelId",
  "provider",
  "capabilities",
  "inputPrice",
  "outputPrice",
  "status",
  "lastTest",
] as const;

// 주소의 조회 조건은 외부 입력이라 검증한다. 허용 목록 밖의 값은 버린다.
const searchSchema = z.object({
  q: z.string().optional().catch(undefined),
  sort: z.enum(SORT_KEYS).optional().catch(undefined),
  order: z.enum(["asc", "desc"]).optional().catch(undefined),
  page: z.number().int().min(1).optional().catch(undefined),
});

export const Route = createFileRoute("/_app/models")({
  validateSearch: searchSchema,
  component: ModelsPage,
});

// 행 타입과 칸 내용은 모델 목록 API의 생성 타입이 생기면 채운다. 그 전까지 행은 비어 있다.
type ModelRow = never;
const EMPTY_CELL = () => null;
// 전체 건수는 목록 API 응답의 total로 바꾼다. 그 전까지의 자리값이다.
const TOTAL_COUNT = 0;

const PRICE_UNIT = <span className="font-normal text-grey-500">(USD/1K)</span>;

const COLUMNS: Column<ModelRow>[] = [
  { key: "name", header: "표시 이름", sortable: true, render: EMPTY_CELL },
  { key: "modelId", header: "Model ID", sortable: true, render: EMPTY_CELL },
  { key: "provider", header: "Provider", sortable: true, render: EMPTY_CELL },
  {
    key: "capabilities",
    header: "지원 기능",
    sortable: true,
    render: EMPTY_CELL,
  },
  {
    key: "inputPrice",
    header: <>Input 가격 {PRICE_UNIT}</>,
    align: "right",
    sortable: true,
    render: EMPTY_CELL,
  },
  {
    key: "outputPrice",
    header: <>Output 가격 {PRICE_UNIT}</>,
    align: "right",
    sortable: true,
    render: EMPTY_CELL,
  },
  { key: "status", header: "상태", sortable: true, render: EMPTY_CELL },
  {
    key: "lastTest",
    header: "마지막 테스트",
    sortable: true,
    render: EMPTY_CELL,
  },
  {
    key: "test",
    header: <span className="sr-only">연결 테스트</span>,
    render: EMPTY_CELL,
  },
];

function ModelsPage() {
  const search = Route.useSearch();
  const navigate = Route.useNavigate();
  const sort =
    search.sort && search.order
      ? { key: search.sort, direction: search.order }
      : undefined;

  return (
    <>
      <div className="flex items-end justify-between gap-6">
        <PageHeader
          title="AI 모델 관리"
          description="사용 가능한 AI 모델을 등록하고 관리할 수 있어요. 등록된 모델은 시뮬레이터에서 사용할 수 있으며, ACTIVE 상태의 모델만 고를 수 있어요."
        />
        <Button icon={plusIcon} disabled>
          신규 모델 등록
        </Button>
      </div>
      <div className="flex flex-wrap gap-3 rounded-2xl bg-white p-4">
        <SearchField
          label="모델 검색"
          placeholder="모델명 또는 Model ID로 검색하세요"
          value={search.q}
          onSearch={(text) =>
            navigate({
              search: (prev) => ({
                ...prev,
                q: text || undefined,
                page: undefined,
              }),
            })
          }
        />
        <Select
          label="Provider"
          value=""
          options={[{ value: "", label: "Provider 전체" }]}
          onChange={() => {}}
          disabled
          className="w-56"
        />
        <Select
          label="상태"
          value=""
          options={[{ value: "", label: "상태 전체" }]}
          onChange={() => {}}
          disabled
          className="w-56"
        />
      </div>
      <SectionCard
        title="등록된 AI 모델"
        count={TOTAL_COUNT}
        description="모델명을 누르면 상세 정보를 볼 수 있어요."
      >
        <DataTable
          caption="등록된 AI 모델"
          columns={COLUMNS}
          rows={[]}
          rowKey={() => ""}
          sort={sort}
          onSortChange={(key) => {
            const next = nextSort(sort, key);
            const sortKey = SORT_KEYS.find((allowed) => allowed === next.key);
            navigate({
              search: (prev) => ({
                ...prev,
                sort: sortKey,
                order: next.direction,
                page: undefined,
              }),
            });
          }}
          empty={<Result title="등록된 모델이 없어요" />}
        />
        <Pagination
          total={TOTAL_COUNT}
          pageSize={PAGE_SIZE}
          page={search.page ?? 1}
          onPageChange={(page) =>
            navigate({ search: (prev) => ({ ...prev, page }) })
          }
        />
      </SectionCard>
    </>
  );
}
