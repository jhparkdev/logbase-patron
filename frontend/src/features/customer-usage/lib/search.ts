import { z } from "zod";
import { periodSchema, recentPeriod } from "../../../shared/lib/period";

/** 기획서의 시연 흐름("최근 30일 조회")과 같은 기본 조회 기간 */
const DEFAULT_PERIOD_DAYS = 30;

/**
 * 주소의 조회 조건은 외부 입력이라 검증한다. 허용하지 않는 값은 버린다.
 * 기간이 없거나 잘못되면, 주소를 읽을 때의 시각으로 KST 최근 30일을 정한다.
 */
export const customerUsageSearchSchema = z
  .object({
    // 문자열이 아닌 값은 여기서 버려 화면이 검증 오류로 멈추지 않게 한다.
    // 날짜 형식과 기간 규칙은 시작일·종료일을 함께 봐야 해서 아래에서 검사한다.
    from: z.string().optional().catch(undefined),
    to: z.string().optional().catch(undefined),
    /** 없으면 요약 화면, 있으면 그 목록의 전체보기 */
    view: z.enum(["customers", "requests"]).optional().catch(undefined),
    /** 상세 패널을 연 고객 번호(customers.customer_id). 요약 화면과 전체보기 어디서든 연다. */
    detail: z.number().int().min(1).optional().catch(undefined),
  })
  .transform(({ from, to, ...rest }) => {
    const period = periodSchema.safeParse({ from, to });
    return {
      ...(period.success
        ? period.data
        : recentPeriod(new Date(), DEFAULT_PERIOD_DAYS)),
      ...rest,
    };
  });

export type CustomerUsageSearch = z.output<typeof customerUsageSearchSchema>;

/** 전체보기로 펼칠 수 있는 목록 */
export type UsageListView = NonNullable<CustomerUsageSearch["view"]>;
