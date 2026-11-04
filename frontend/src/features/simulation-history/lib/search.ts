import { z } from "zod";
import type { components } from "../../../shared/api/schema";
import { formatKstDateTime } from "../../../shared/lib/format";
import { PAGE_SIZE } from "../../../shared/lib/pagination";

const DAY_MS = 86_400_000;
const DEFAULT_DAYS = 30;
export const HISTORY_MAX_DAYS = 366;
// 서버 허용 목록(HistorySortColumn)에 있는 값만 둔다.
export const HISTORY_SORTS = [
  "requestedAt",
  "id",
  "scenario",
  "modelCount",
  "status",
  "costStatus",
  "totalCost",
] as const satisfies readonly components["schemas"]["HistorySortColumn"][];
export const HISTORY_STATUSES = [
  "all",
  "PENDING",
  "RUNNING",
  "SUCCESS",
  "PARTIAL_SUCCESS",
  "FAILED",
  "CANCELLED",
] as const;
export const STATUS_LABELS: Record<(typeof HISTORY_STATUSES)[number], string> =
  {
    all: "전체",
    PENDING: "대기",
    RUNNING: "진행 중",
    SUCCESS: "성공",
    PARTIAL_SUCCESS: "부분 성공",
    FAILED: "실패",
    CANCELLED: "취소",
  };
const date = z
  .string()
  .regex(/^\d{4}-\d{2}-\d{2}$/, "날짜를 선택해 주세요.")
  .refine((value) => {
    const parsed = new Date(`${value}T00:00:00Z`);
    return (
      Number.isFinite(parsed.getTime()) &&
      parsed.toISOString().slice(0, 10) === value
    );
  }, "올바른 날짜를 선택해 주세요.");
const key = z.string().trim().max(128, "128자 이내로 입력해 주세요.");
const simulationId = key.refine(
  (value) => value === "" || z.guid().safeParse(value).success,
  "실행 ID 형식을 확인해 주세요.",
);
export const historyFiltersSchema = z
  .object({
    from: date,
    to: date,
    scenario: key,
    model: key,
    status: z.enum(HISTORY_STATUSES),
    simulationId,
  })
  .superRefine((value, ctx) => {
    const days = (Date.parse(value.to) - Date.parse(value.from)) / DAY_MS + 1;
    if (days < 1)
      ctx.addIssue({
        code: "custom",
        path: ["from"],
        message: "시작일은 종료일보다 늦을 수 없어요.",
      });
    if (days > HISTORY_MAX_DAYS)
      ctx.addIssue({
        code: "custom",
        path: ["to"],
        message: `${HISTORY_MAX_DAYS}일 이내로 조회해 주세요.`,
      });
  });
export type HistoryFilters = z.infer<typeof historyFiltersSchema>;
export function recentHistoryFilters(now = new Date()): HistoryFilters {
  const to = formatKstDateTime(now.toISOString()).slice(0, 10);
  const from = new Date(Date.parse(to) - (DEFAULT_DAYS - 1) * DAY_MS)
    .toISOString()
    .slice(0, 10);
  return { from, to, scenario: "", model: "", status: "all", simulationId: "" };
}
export function createHistorySearchSchema(now = new Date()) {
  const defaults = recentHistoryFilters(now);
  return z
    .object({
      from: date.catch(defaults.from),
      to: date.catch(defaults.to),
      scenario: key.catch(""),
      model: key.catch(""),
      simulationId: simulationId.catch(""),
      status: z.enum(HISTORY_STATUSES).catch("all"),
      sort: z.enum(HISTORY_SORTS).catch("requestedAt"),
      direction: z.enum(["asc", "desc"]).catch("desc"),
      page: z.number().int().min(1).catch(1),
      selected: z.guid().optional().catch(undefined),
      detail: z.boolean().catch(false),
    })
    .transform((value) => {
      const valid = historyFiltersSchema.safeParse(value);
      return {
        ...value,
        ...(!valid.success ? { from: defaults.from, to: defaults.to } : {}),
        detail: !!value.selected && value.detail,
      };
    });
}
export const historySearchSchema = createHistorySearchSchema();
export type HistorySearch = z.output<typeof historySearchSchema>;

const NUMERIC_ID = /^\d+$/;
/** 고르지 않은 조건과 숫자 ID가 아닌 값은 보내지 않는다. 서버가 거절하면 목록 전체가 실패로 보인다. */
export function historyListQuery(search: HistorySearch) {
  return {
    start_date: search.from,
    end_date: search.to,
    page: search.page,
    page_size: PAGE_SIZE,
    sort: search.sort,
    direction: search.direction,
    ...(NUMERIC_ID.test(search.scenario)
      ? { scenario_id: Number(search.scenario) }
      : {}),
    ...(NUMERIC_ID.test(search.model)
      ? { model_id: Number(search.model) }
      : {}),
    ...(search.status !== "all" ? { status: search.status } : {}),
    ...(search.simulationId ? { simulation_id: search.simulationId } : {}),
  };
}
export function changeHistorySort(
  search: HistorySearch,
  sort: HistorySearch["sort"],
): HistorySearch {
  return {
    ...search,
    page: 1,
    sort,
    direction:
      search.sort === sort && search.direction === "asc" ? "desc" : "asc",
  };
}
