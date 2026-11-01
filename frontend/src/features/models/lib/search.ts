import { z } from "zod";
import type { components } from "../../../shared/api/schema";
import { PAGE_SIZE } from "../../../shared/lib/pagination";
import type { SortDirection, SortState } from "../../../shared/lib/sort";
import { MODEL_STATUSES } from "./view";

type ModelSortField = components["schemas"]["ModelSortField"];

// 정렬 칸이 쓰는 값. 백엔드 ModelSortField의 부분집합이어야 함
const SORT_KEYS = [
  "display_name",
  "openrouter_model_id",
  "provider",
  "input_modalities",
  "price_input",
  "price_output",
  "status",
  "last_test_at",
] as const satisfies readonly ModelSortField[];
type ModelSortKey = (typeof SORT_KEYS)[number];
const ORDERS = ["asc", "desc"] as const;

// 백엔드(schemas/models.py)의 검색어 길이·페이지 상한과 동일. 초과 시 요청 거절
const MAX_QUERY_LENGTH = 100;
const MAX_PAGE = 100_000;

// 검색어와 제공사가 함께 쓰는 문자열 규칙
export const searchTextSchema = z
  .string()
  .min(1)
  .max(MAX_QUERY_LENGTH)
  // NUL 문자는 PostgreSQL이 거절하므로 백엔드와 같이 차단
  .refine((text) => !text.includes("\0"));

/** 주소 조건은 외부 입력이라 검증. 허용 밖의 값은 버림 */
export const modelsSearchSchema = z.object({
  q: searchTextSchema.optional().catch(undefined),
  provider: searchTextSchema.optional().catch(undefined),
  status: z.enum(MODEL_STATUSES).optional().catch(undefined),
  sort: z.enum(SORT_KEYS).optional().catch(undefined),
  order: z.enum(ORDERS).optional().catch(undefined),
  page: z.number().int().min(1).max(MAX_PAGE).optional().catch(undefined),
  /** 상세 패널을 연 모델 번호(models.model_id) */
  model: z.number().int().min(1).optional().catch(undefined),
});

export type ModelsSearch = z.output<typeof modelsSearchSchema>;

/** 정렬 값·방향이 모두 있어야 정렬 상태. 없으면 서버 기본 정렬 */
export function modelSortOf(
  search: ModelsSearch,
): { key: ModelSortKey; direction: SortDirection } | undefined {
  return search.sort && search.order
    ? { key: search.sort, direction: search.order }
    : undefined;
}

/** 주소 조건을 GET /api/models 쿼리로 변환. undefined는 요청에서 제외 */
export function modelListQuery(search: ModelsSearch) {
  const sort = modelSortOf(search);
  return {
    q: search.q,
    provider: search.provider,
    status: search.status ? [search.status] : undefined,
    sort: sort?.key,
    order: sort?.direction,
    page: search.page ?? 1,
    page_size: PAGE_SIZE,
  };
}

/** 정렬 변경 시 1페이지로 복귀 */
export function modelSortParams(sort: SortState) {
  return {
    sort: sort.key as ModelSortKey,
    order: sort.direction,
    page: undefined,
  };
}

/** 검색어·제공사·상태 중 하나라도 있으면 조건이 걸린 상태 */
export function hasModelFilter(search: ModelsSearch): boolean {
  return (
    search.q !== undefined ||
    search.provider !== undefined ||
    search.status !== undefined
  );
}
