import { expect, test } from "vitest";
import { simulatorSearchSchema } from "./search";

const RUN_ID = "01a1611f-3e80-73c5-a130-3efa5a1f75de";

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

test("실행 ID는 UUID만 받아 새로고침해도 결과를 다시 찾는다", () => {
  expect(
    simulatorSearchSchema.parse({ run: RUN_ID, sourceRun: RUN_ID }),
  ).toMatchObject({ run: RUN_ID, sourceRun: RUN_ID });
  const invalid = simulatorSearchSchema.parse({
    run: "run-1",
    sourceRun: "run-1",
  });
  expect(invalid.run).toBeUndefined();
  expect(invalid.sourceRun).toBeUndefined();
});
