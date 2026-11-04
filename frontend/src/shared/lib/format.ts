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

function kstParts(utc: string) {
  const date = new Date(utc);
  if (Number.isNaN(date.getTime())) {
    throw new Error("시각으로 읽을 수 없는 값입니다.");
  }
  return Object.fromEntries(
    KST_PARTS.formatToParts(date).map(({ type, value }) => [type, value]),
  );
}

/** 서버가 준 UTC 시각을 KST "YYYY-MM-DD HH:mm:ss"로 표시한다. */
export function formatKstDateTime(utc: string): string {
  const part = kstParts(utc);
  return `${part.year}-${part.month}-${part.day} ${part.hour}:${part.minute}:${part.second}`;
}

/** 서버가 준 UTC 시각을 KST 날짜 "YYYY-MM-DD"로 표시한다. 결제 기간처럼 날짜만 보여 줄 때 쓴다. */
export function formatKstDate(utc: string): string {
  const part = kstParts(utc);
  return `${part.year}-${part.month}-${part.day}`;
}

const GROUPING = new Intl.NumberFormat("ko-KR");

/** 시안 기준 소수 자릿수: 합계·요약은 2자리, 호출 1건 비용은 4자리. */
const USD_DIGITS = { summary: 2, perCall: 4 } as const;

/** USD 금액의 소수 자릿수 종류. summary는 합계·요약, perCall은 호출 1건. */
export type UsdPrecision = keyof typeof USD_DIGITS;

const DECIMAL_STRING = /^\d+(\.\d+)?$/;

/** 0이 아닌 금액이 자릿수에 걸려 0으로 보일 때 남기는 유효숫자 수. */
const SMALL_AMOUNT_SIGNIFICANT_DIGITS = 2;

/** 금액 × 10^digits 를 정수로 만들어 반올림한다. 예: 0.12345, 4자리 → 1234 + 1 = 1235 */
function scaleAndRound(whole: string, fraction: string, digits: number) {
  const padded = fraction.padEnd(digits + 1, "0");
  const roundUp = Number(padded[digits]) >= 5;
  return BigInt(whole + padded.slice(0, digits)) + (roundUp ? 1n : 0n);
}

/**
 * API가 문자열로 준 USD 금액을 자릿수에 맞춰 반올림(사사오입)해 표시한다.
 * float 오차를 피하려고 숫자로 바꾸지 않고 정수(BigInt)로 계산한다.
 * 0이 아닌 금액이 0으로 반올림되면 실제 지출을 숨기게 되므로 자릿수를 늘려 보여 준다.
 * 미확인 비용(null)은 받지 않는다. 미확인 표시는 화면이 따로 한다.
 */
export function formatUsd(amount: string, precision: UsdPrecision): string {
  if (!DECIMAL_STRING.test(amount)) {
    throw new Error("금액 형식이 아닌 값입니다.");
  }
  const [whole, fraction = ""] = amount.split(".");
  let digits: number = USD_DIGITS[precision];
  let scaled = scaleAndRound(whole, fraction, digits);
  const stored = fraction.replace(/0+$/, "");
  if (scaled === 0n && stored) {
    const firstNonZero = stored.search(/[1-9]/);
    digits = Math.min(
      firstNonZero + SMALL_AMOUNT_SIGNIFICANT_DIGITS,
      stored.length,
    );
    scaled = scaleAndRound(whole, fraction, digits);
  }

  const scaledText = scaled.toString().padStart(digits + 1, "0");
  const wholeText = GROUPING.format(BigInt(scaledText.slice(0, -digits)));
  return `${wholeText}.${scaledText.slice(-digits)}`;
}

/** 건수와 토큰 수에 천 단위 쉼표를 붙인다. */
export function formatCount(count: number): string {
  return GROUPING.format(count);
}

const ZERO_AMOUNT = /^0+(\.0+)?$/;

/** API가 문자열로 준 금액이 0인지. 추정 금액이 0이면 ≈를 붙이지 않을 때 쓴다. */
export function isZeroAmount(amount: string): boolean {
  return ZERO_AMOUNT.test(amount);
}

/** 금액에 넣지 못한 비용 미확인 호출 수 안내. 미확인이 없으면 문구가 없다. */
export function unreflectedText(unknownCount: number): string | undefined {
  return unknownCount > 0 ? `미확인 ${unknownCount}건 미반영` : undefined;
}
