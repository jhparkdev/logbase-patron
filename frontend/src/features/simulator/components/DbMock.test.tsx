// @vitest-environment jsdom
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, expect, test } from "vitest";
import { dbMock } from "./dbMock.fixture";
import { SimulationResults } from "./SimulationResults";

afterEach(cleanup);

test.each(dbMock.runs)(
  "기존 DB mock $key의 실행·비용·검증 상태 표시",
  (run) => {
    render(<SimulationResults view={{ kind: "ready", run }} />);
    expect(
      screen.getByRole("heading", { name: "시뮬레이션 결과 요약" }),
    ).toBeDefined();
    expect(screen.getAllByText(run.status.label).length).toBeGreaterThan(0);
    for (const slot of run.slots) {
      expect(screen.getAllByText(slot.name).length).toBeGreaterThan(0);
      expect(screen.getAllByText(slot.status.label).length).toBeGreaterThan(0);
      expect(screen.getAllByText(slot.schemaValidation).length).toBeGreaterThan(
        0,
      );
      if (slot.cost.kind === "unknown")
        expect(screen.getAllByText("미확인").length).toBeGreaterThan(0);
      if (slot.cost.kind === "estimated")
        expect(screen.getAllByText("추정").length).toBeGreaterThan(0);
    }
    if (run.unknownCostCount > 0)
      expect(
        screen.getByText(`미확인 ${run.unknownCostCount}건 미반영`),
      ).toBeDefined();
  },
);
