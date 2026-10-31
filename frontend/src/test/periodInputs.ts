import { fireEvent, screen } from "@testing-library/react";
import type { Period } from "../shared/lib/period";

/** 조회 조건의 시작일·종료일 칸. 화면이 그려질 때까지 기다린다. */
export async function periodInputs() {
  return {
    from: await screen.findByLabelText<HTMLInputElement>("시작일"),
    to: screen.getByLabelText<HTMLInputElement>("종료일"),
  };
}

/** 시작일·종료일 칸에 기간을 입력한다. */
export async function changePeriod(period: Period) {
  const { from, to } = await periodInputs();
  fireEvent.change(from, { target: { value: period.from } });
  fireEvent.change(to, { target: { value: period.to } });
}
