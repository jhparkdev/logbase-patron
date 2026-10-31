const KST_PARTS = new Intl.DateTimeFormat("ko-KR", {
  timeZone: "Asia/Seoul",
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
  hour: "2-digit",
  minute: "2-digit",
  second: "2-digit",
  hourCycle: "h23",
});

/** 서버가 준 UTC 시각을 KST "YYYY-MM-DD HH:mm:ss"로 표시한다. */
export function formatKstDateTime(utc: string): string {
  const date = new Date(utc);
  if (Number.isNaN(date.getTime())) {
    throw new Error("시각으로 읽을 수 없는 값입니다.");
  }
  const part = Object.fromEntries(
    KST_PARTS.formatToParts(date).map(({ type, value }) => [type, value]),
  );
  return `${part.year}-${part.month}-${part.day} ${part.hour}:${part.minute}:${part.second}`;
}

const GROUPING = new Intl.NumberFormat("ko-KR");

/** 시안 기준 소수 자릿수: 합계·요약은 2자리, 호출 1건 비용은 4자리. */
const USD_DIGITS = { summary: 2, perCall: 4 } as const;

/** USD 금액의 소수 자릿수 종류. summary는 합계·요약, perCall은 호출 1건. */
export type UsdPrecision = keyof typeof USD_DIGITS;

const DECIMAL_STRING = /^\d+(\.\d+)?$/;

/**
 * API가 문자열로 준 USD 금액을 자릿수에 맞춰 반올림(사사오입)해 표시한다.
 * float 오차를 피하려고 숫자로 바꾸지 않고 정수(BigInt)로 계산한다.
 * 미확인 비용(null)은 받지 않는다. 미확인 표시는 화면이 따로 한다.
 */
export function formatUsd(amount: string, precision: UsdPrecision): string {
  if (!DECIMAL_STRING.test(amount)) {
    throw new Error("금액 형식이 아닌 값입니다.");
  }
  const digits = USD_DIGITS[precision];
  const [whole, fraction = ""] = amount.split(".");
  const padded = fraction.padEnd(digits + 1, "0");
  const roundUp = Number(padded[digits]) >= 5;
  // 금액 × 10^digits 를 정수로 만든 뒤 반올림한다. 예: 0.12345, 4자리 → 1234 + 1 = 1235
  const scaled = BigInt(whole + padded.slice(0, digits)) + (roundUp ? 1n : 0n);

  const scaledText = scaled.toString().padStart(digits + 1, "0");
  const wholeText = GROUPING.format(BigInt(scaledText.slice(0, -digits)));
  return `${wholeText}.${scaledText.slice(-digits)}`;
}

/** 건수와 토큰 수에 천 단위 쉼표를 붙인다. */
export function formatCount(count: number): string {
  return GROUPING.format(count);
}
