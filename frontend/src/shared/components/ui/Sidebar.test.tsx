// @vitest-environment jsdom
import { screen, within } from "@testing-library/react";
import { expect, test } from "vitest";
import { renderAt } from "../../../test/renderAt";

function findNav() {
  return screen.findByRole("navigation", { name: "주 메뉴" });
}

test("메뉴 5개가 각 화면 주소로 연결된다", async () => {
  renderAt("/customer-usage");

  const links = within(await findNav())
    .getAllByRole("link")
    .map((link) => [link.textContent, link.getAttribute("href")]);

  expect(links).toEqual([
    ["고객 AI 사용 현황", "/customer-usage"],
    ["내부 AI 예산 관리", "/internal-budget"],
    ["AI 모델 관리", "/models"],
    ["AI 모델 시뮬레이터", "/simulator"],
    ["시뮬레이션 결과 이력", "/simulation-history"],
  ]);
});

test("현재 화면의 메뉴만 선택 상태로 표시한다", async () => {
  renderAt("/models");

  const current = within(await findNav())
    .getAllByRole("link")
    .filter((link) => link.getAttribute("aria-current") === "page")
    .map((link) => link.textContent);

  expect(current).toEqual(["AI 모델 관리"]);
});
