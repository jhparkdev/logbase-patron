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
    from: z.string().optional().catch(undefined),
    to: z.string().optional().catch(undefined),
    /** 없으면 요약 화면, 있으면 그 목록의 전체보기 */
    view: z.enum(["customers", "requests"]).optional().catch(undefined),
  })
  .transform(({ from, to, view }) => {
    const period = periodSchema.safeParse({ from, to });
    return {
      ...(period.success
        ? period.data
        : recentPeriod(new Date(), DEFAULT_PERIOD_DAYS)),
      view,
    };
  });

export type CustomerUsageSearch = z.output<typeof customerUsageSearchSchema>;
