import { dbMock } from "../../src/features/simulator/components/dbMock.fixture";
import { createDefaultValues } from "../../src/features/simulator/lib/form";

// 같은 실행의 입력은 추적 중인 seed의 simulation_runs, 결과는 기존 DB 스냅샷에서 복원한다.
// backend/seed/patron_mock_data_v0.6.sql: 01a1611f-3e80-73c5-a130-3efa5a1f75de
const run = dbMock.runs.find(
  (item) => item.key === "01a1611f-3e80-73c5-a130-3efa5a1f75de",
);
const scenario = dbMock.scenarios.find((item) => item.key === "3");
if (!run || !scenario)
  throw new Error("P-04 예시의 기존 mock 기록이 없습니다.");

const selections = run.slots.map((slot) => {
  const choice = dbMock.choices.find(
    (item) => item.name === slot.name && item.provider === slot.provider,
  );
  if (!choice) throw new Error("P-04 예시의 모델 선택 정보가 없습니다.");
  return choice.key;
});

export const previewData = {
  run,
  choices: dbMock.choices,
  scenarios: dbMock.scenarios,
  initialValues: createDefaultValues({
    mode: "scenario",
    scenarioKey: scenario.key,
    prompt: scenario.prompt,
    text: "상품명: 린넨 셔츠 원피스 / 가격 59,000원 / 옵션: 베이지, 네이비 / 소재: 린넨 100%",
    temperature: "0.3",
    maxTokens: "512",
    selections,
  }),
};
