import { expect, test } from "vitest";
import { assistantPageContext, pageContextLabel } from "./page-context";

test("P01 carries applied filters without unrelated or unsaved values", () => {
  expect(
    assistantPageContext("/customer-usage", {
      from: "2026-10-01",
      to: "2026-10-20",
      customer: 2,
      service: 3,
      model: 4,
      view: "requests",
      password: "must-not-be-sent",
      project: 99,
    }),
  ).toEqual({
    page: "customer_usage",
    start_date: "2026-10-01",
    end_date: "2026-10-20",
    customer_id: 2,
    service_id: 3,
    model_id: 4,
    section: "requests",
  });
});

test("selected customer and project panels use their whole budget month", () => {
  expect(
    assistantPageContext("/customer-usage", {
      from: "2026-10-01",
      to: "2026-10-20",
      customer: 1,
      detail: 2,
      service: 3,
      model: 4,
    }),
  ).toEqual({
    page: "customer_usage",
    start_date: "2026-10-01",
    end_date: "2026-10-31",
    customer_id: 2,
    section: "budgets",
    detail: true,
  });
  expect(
    assistantPageContext("/internal-budget", {
      from: "2026-02-10",
      to: "2026-02-20",
      project: 1,
      detail: 2,
      model: 4,
    }),
  ).toEqual({
    page: "internal_budget",
    start_date: "2026-02-01",
    end_date: "2026-02-28",
    project_id: 2,
    section: "budgets",
    detail: true,
  });
});

test("execution and model selections are scoped to their screens", () => {
  const id = "00000000-0000-4000-8000-000000000001";
  expect(
    assistantPageContext("/simulation-history", { selected: id, model: "2" }),
  ).toMatchObject({
    page: "simulation_history",
    simulation_id: id,
    model_id: 2,
  });
  expect(assistantPageContext("/models", { model: 2 })).toEqual({
    page: "models",
    model_id: 2,
  });
  expect(assistantPageContext("/unknown", {})).toBeUndefined();
});

test("context labels make scope and period visible without exposing IDs", () => {
  const label = pageContextLabel({
    page: "customer_usage",
    customer_id: 999,
    start_date: "2026-10-01",
    end_date: "2026-10-31",
  });
  expect(label).toContain("고객 사용 현황");
  expect(label).toContain("2026-10-01 ~ 2026-10-31");
  expect(label).not.toContain("999");
});
