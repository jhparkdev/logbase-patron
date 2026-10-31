import { expect, test } from "vitest";
import { simulatorSearchSchema } from "./search";

test("정렬 조건을 검증하고 잘못된 검색값을 기본값으로 복구한다", () => {
  expect(simulatorSearchSchema.parse({})).toEqual({
    sort: "model",
    direction: "asc",
  });
  expect(
    simulatorSearchSchema.parse({ sort: "cost", direction: "desc" }),
  ).toEqual({ sort: "cost", direction: "desc" });
  expect(simulatorSearchSchema.parse({ sort: "sql", direction: [] })).toEqual({
    sort: "model",
    direction: "asc",
  });
});
