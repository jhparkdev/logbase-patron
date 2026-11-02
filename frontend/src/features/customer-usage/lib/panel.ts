const FULL_PERCENT = 100;

/** 요약 카드의 남은 예산 줄. 예산이 없으면 두지 않고, 넘었으면 음수 대신 초과 금액으로 보여 준다. */
export function remainingBudget(remaining: string | null) {
  if (remaining === null) {
    return undefined;
  }
  return remaining.startsWith("-")
    ? { label: "초과 금액", amount: remaining.slice(1), over: true }
    : { label: "남은 예산", amount: remaining, over: false };
}

/** 서비스가 고객 예산에서 차지하는 비중. 글자는 실제 비중, 막대는 100%에서 멈춘다. */
export function serviceBudgetShare(sharePct: string | null): {
  label: string;
  width?: number;
} {
  if (sharePct === null) {
    return { label: "예산 미설정" };
  }
  const percent = Math.round(Number(sharePct));
  return {
    label: `예산의 ${percent}%`,
    width: Math.min(percent, FULL_PERCENT),
  };
}
