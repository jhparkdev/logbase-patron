import { z } from "zod";
import { formatKstDateTime } from "./format";

const DAY_MS = 86_400_000;

/** 조회 기간의 최대 일수(시작일·종료일 포함). 백엔드 services/simulation_period.py의 MAX_PERIOD_DAYS와 같아야 한다. */
export const MAX_PERIOD_DAYS = 366;

/** KST 달력의 날짜 "YYYY-MM-DD"로 나타낸 조회 기간. 시작일과 종료일을 모두 포함한다. */
export type Period = { from: string; to: string };

/** 현재 시각이 KST 달력으로 며칠인지. */
export function kstToday(now: Date): string {
  return formatKstDateTime(now.toISOString()).slice(0, 10);
}

/** KST 기준 이번 달 1일부터 오늘까지. */
export function currentMonthPeriod(now: Date): Period {
  const today = kstToday(now);
  return { from: `${today.slice(0, 8)}01`, to: today };
}

/** 선택한 날짜가 속한 예산 월 전체. UTC 달력 계산으로 브라우저 시간대 영향을 피한다. */
export function wholeMonthPeriod(day: string): Period {
  const [year, month] = day.split("-").map(Number);
  return {
    from: `${day.slice(0, 7)}-01`,
    to: new Date(Date.UTC(year, month, 0)).toISOString().slice(0, 10),
  };
}

function toUtcMidnight(date: string): number {
  return Date.parse(`${date}T00:00:00Z`);
}

/** KST 오늘을 포함한 최근 days일. 백엔드 services/simulation_period.py의 기본 기간과 같은 방식이다. */
export function recentPeriod(now: Date, days: number): Period {
  const today = kstToday(now);
  const from = new Date(toUtcMidnight(today) - (days - 1) * DAY_MS)
    .toISOString()
    .slice(0, 10);
  return { from, to: today };
}

const calendarDate = z
  .string()
  .refine(
    (value) =>
      /^\d{4}-\d{2}-\d{2}$/.test(value) &&
      new Date(toUtcMidnight(value)).toISOString().startsWith(value),
    "날짜를 선택해 주세요.",
  );

export const periodSchema = z
  .object({ from: calendarDate, to: calendarDate })
  .superRefine(({ from, to }, ctx) => {
    const days = (toUtcMidnight(to) - toUtcMidnight(from)) / DAY_MS + 1;
    if (days < 1) {
      ctx.addIssue({
        code: "custom",
        path: ["from"],
        message: "시작일은 종료일보다 늦을 수 없어요.",
      });
    } else if (days > MAX_PERIOD_DAYS) {
      ctx.addIssue({
        code: "custom",
        path: ["to"],
        message: `기간은 최대 ${MAX_PERIOD_DAYS}일까지 조회할 수 있어요. 기간을 줄여 주세요.`,
      });
    }
  });
