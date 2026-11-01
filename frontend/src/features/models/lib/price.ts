const DECIMAL_STRING = /^\d+(\.\d+)?$/;
/** 100만 토큰 = 토큰 1개의 10^6배, 소수점 6자리 이동 */
const SHIFT_DIGITS = 6;
const MIN_FRACTION_DIGITS = 2;

/**
 * 토큰당 단가(USD 문자열)를 100만 토큰당 단가로 변환.
 * 숫자 변환 시 오차가 생겨 문자열 소수점만 이동, 소수 둘째 자리까지 0 채움.
 */
export function formatPricePerMillion(perToken: string): string {
  if (!DECIMAL_STRING.test(perToken)) {
    throw new Error("금액 형식이 아닌 값입니다.");
  }
  const [whole, fraction = ""] = perToken.split(".");
  const padded = fraction.padEnd(SHIFT_DIGITS, "0");
  const shiftedWhole = BigInt(whole + padded.slice(0, SHIFT_DIGITS));
  const shiftedFraction = padded
    .slice(SHIFT_DIGITS)
    .replace(/0+$/, "")
    .padEnd(MIN_FRACTION_DIGITS, "0");
  return `${shiftedWhole}.${shiftedFraction}`;
}
