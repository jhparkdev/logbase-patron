// @vitest-environment jsdom
import { fireEvent, screen, waitFor } from "@testing-library/react";
import { expect, test } from "vitest";
import { renderAt } from "../../test/renderAt";

type Router = ReturnType<typeof renderAt>;

/** 화면이 검증을 거쳐 실제로 쓰는 조회 조건 */
function appliedSearch(router: Router) {
  return router.state.matches.find(
    (match) => match.routeId === "/_app/internal-budget",
  )?.search;
}

async function periodInputs() {
  return {
    from: await screen.findByLabelText<HTMLInputElement>("시작일"),
    to: screen.getByLabelText<HTMLInputElement>("종료일"),
  };
}

test("주소의 기간을 칸에 보여 준다", async () => {
  renderAt("/internal-budget?from=2026-10-01&to=2026-10-15");

  const { from, to } = await periodInputs();
  expect(from.value).toBe("2026-10-01");
  expect(to.value).toBe("2026-10-15");
});

test("조회를 눌러야 바꾼 기간이 주소에 남는다", async () => {
  const router = renderAt("/internal-budget?from=2026-10-01&to=2026-10-15");
  const { from, to } = await periodInputs();

  fireEvent.change(from, { target: { value: "2026-09-01" } });
  fireEvent.change(to, { target: { value: "2026-09-30" } });
  expect(appliedSearch(router)).toEqual({
    from: "2026-10-01",
    to: "2026-10-15",
  });

  fireEvent.click(screen.getByRole("button", { name: "조회" }));

  await waitFor(() =>
    expect(appliedSearch(router)).toEqual({
      from: "2026-09-01",
      to: "2026-09-30",
    }),
  );
});

test("366일을 넘는 기간은 조회하지 않고 줄여 달라고 안내한다", async () => {
  const router = renderAt("/internal-budget?from=2026-10-01&to=2026-10-15");
  const { from, to } = await periodInputs();

  fireEvent.change(from, { target: { value: "2025-01-01" } });
  fireEvent.change(to, { target: { value: "2026-01-02" } });
  fireEvent.click(screen.getByRole("button", { name: "조회" }));

  expect((await screen.findByRole("alert")).textContent).toBe(
    "기간은 최대 366일까지 조회할 수 있어요. 기간을 줄여 주세요.",
  );
  expect(appliedSearch(router)).toEqual({
    from: "2026-10-01",
    to: "2026-10-15",
  });
});
