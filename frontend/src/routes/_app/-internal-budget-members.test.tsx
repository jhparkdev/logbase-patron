// @vitest-environment jsdom
import { fireEvent, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, expect, test, vi } from "vitest";
import { stubInternalBudgetApi } from "../../test/internalBudgetApi";
import { renderAt } from "../../test/renderAt";

const OCTOBER = "/internal-budget?from=2026-10-01&to=2026-10-31";
const TITLE = "구성원별 Command Code 사용량";

beforeEach(() => {
  stubInternalBudgetApi();
});

afterEach(() => vi.restoreAllMocks());

test("구성원 줄에 결제 기간 기준 사용량을 서버 값 그대로 보여 주고, 조회 기간은 보내지 않는다", async () => {
  const { requests } = stubInternalBudgetApi();
  renderAt(OCTOBER);

  const table = await screen.findByRole("table", { name: TITLE });
  const row = (await within(table).findByText("홍길동")).closest("tr");
  expect(row).not.toBeNull();
  const cells = within(row as HTMLElement)
    .getAllByRole("cell")
    .map((cell) => cell.textContent);
  expect(cells).toEqual([
    "홍길동",
    "27.65",
    "2,379",
    "816,632,167",
    "1,987,270",
    "62.37",
    "2026-10-20 ~ 2026-11-20",
    "2026-11-03 10:00:00",
  ]);
  const request = requests.find(
    ({ url }) => url.pathname === "/api/usage/internal/command-code",
  );
  expect(request?.url.search).toBe("");
});

test("불러오지 못한 구성원은 값 대신 이유 배지를 보여 주고 0으로 적지 않는다", async () => {
  renderAt(OCTOBER);

  const table = await screen.findByRole("table", { name: TITLE });
  const row = (await within(table).findByText("김철수")).closest("tr");
  const cells = within(row as HTMLElement)
    .getAllByRole("cell")
    .map((cell) => cell.textContent);
  expect(cells.slice(1, 7)).toEqual(["–", "–", "–", "–", "–", "–"]);
  expect(cells[7]).toBe("2026-11-03 10:00:00");
  expect(within(row as HTMLElement).getByText("Key 없음")).toBeTruthy();
});

test("등록된 구성원이 없으면 등록되면 보인다고 알린다", async () => {
  stubInternalBudgetApi({ commandCode: { status: 200, body: { items: [] } } });
  renderAt(OCTOBER);

  expect(await screen.findByText("등록된 구성원 키가 없어요")).toBeTruthy();
});

test("구성원 사용량을 불러오지 못하면 그 블록에만 알리고 다시 시도할 수 있다", async () => {
  const { replies } = stubInternalBudgetApi({
    commandCode: { status: 500, body: {} },
  });
  // 오류 경계가 받는 오류를 React가 출력한다. 예상한 동작이라 테스트 출력에 남기지 않는다.
  vi.spyOn(console, "error").mockImplementation(() => {});
  renderAt(OCTOBER);

  expect(
    await screen.findByText("구성원 사용량을 불러오지 못했어요"),
  ).toBeTruthy();
  expect(
    await screen.findByRole("table", { name: "구독료 관리" }),
  ).toBeTruthy();

  delete replies.commandCode;
  fireEvent.click(screen.getByRole("button", { name: "다시 시도" }));

  expect(await screen.findByRole("table", { name: TITLE })).toBeTruthy();
});
