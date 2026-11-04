import { formatKstDateTime, formatUsd } from "./format";

const ISO_DATE_TIME =
  /(?<![\w/])\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})(?![\w:+-])/g;
const COUNT = /(?<![\w.,])(\d{4,})([ \t]*)(토큰|건|개)(?![A-Za-z0-9_])/g;
const USD = /(?<![\w])\$(\d+(?:\.\d+)?)(?![\w,]|\.\d)/g;
const GROUPING = new Intl.NumberFormat("ko-KR");

function readableDateTime(source: string): string {
  const [year, month, day] = source.slice(0, 10).split("-").map(Number);
  // Date가 잘못된 날짜(예: 2월 30일)를 다음 달로 보정하지 않도록 한다.
  if (
    month < 1 ||
    month > 12 ||
    day < 1 ||
    day > new Date(Date.UTC(year, month, 0)).getUTCDate()
  )
    return source;
  try {
    const [date, time] = formatKstDateTime(source).split(" ");
    const [kstYear, kstMonth, kstDay] = date.split("-");
    return `${kstYear}년 ${Number(kstMonth)}월 ${Number(kstDay)}일 ${time} (한국시간)`;
  } catch {
    return source;
  }
}

/** 답변 본문 표시만 바꾼다. 원문·코드·대화 요청 데이터에는 적용하지 않는다. */
export function formatAssistantProse(content: string): string {
  return content
    .replace(ISO_DATE_TIME, readableDateTime)
    .replace(
      COUNT,
      (_match, digits: string, gap: string, unit: string) =>
        `${GROUPING.format(BigInt(digits))}${gap}${unit}`,
    )
    .replace(
      USD,
      (_match, amount: string) => `$${formatUsd(amount, "perCall")}`,
    );
}
