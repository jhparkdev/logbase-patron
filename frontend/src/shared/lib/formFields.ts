import { z } from "zod";

const MONTH = /^\d{4}-(0[1-9]|1[0-2])$/;
const DECIMAL = /^-?\d+(\.\d+)?$/;

/** 연-월 "YYYY-MM". 월 입력 칸(type="month")의 값이다. */
export function monthField(message: string) {
  return z.string().regex(MONTH, message);
}

/** USD 금액. 숫자로 바꾸지 않고 문자열 그대로 검증하고 보낸다(float 오차 방지). */
export function usdAmountField(emptyMessage: string) {
  return z
    .string()
    .trim()
    .min(1, emptyMessage)
    .regex(DECIMAL, "숫자로 입력해 주세요.");
}
