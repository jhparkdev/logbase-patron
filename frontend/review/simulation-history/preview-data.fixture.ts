import type {
  HistoryDetailView,
  HistoryRow,
} from "../../src/features/simulation-history/lib/presentation";
import type { HistorySearch } from "../../src/features/simulation-history/lib/search";
import { dbMock } from "../../src/features/simulator/components/dbMock.fixture";
import { createComparisons } from "../../src/features/simulator/lib/comparisons";
import { createDefaultValues } from "../../src/features/simulator/lib/form";
import type { RunView } from "../../src/features/simulator/lib/presentation";
import { historyInputSnapshots } from "./history-inputs.fixture";

type Snapshot = {
  scenarioKey: string;
  mode: "custom" | "scenario";
  prompt: string | null;
  text: string | null;
  jsonSchema: string;
  temperature: string;
  maxTokens: string;
  routingPolicy: string;
  status: string;
  rerunOf: string | null;
  attachments: readonly { key: string; name: string; available: boolean }[];
};
const snapshots: Record<string, Snapshot> = historyInputSnapshots;
const DAY_MS = 86_400_000;
const choiceFor = (slot: RunView["slots"][number]) =>
  dbMock.choices.find(
    (choice) => choice.name === slot.name && choice.provider === slot.provider,
  );

export const historyRows: HistoryRow[] = dbMock.runs.map((run) => ({
  key: run.key,
  requestedAt: run.requestedAt,
  scenario:
    dbMock.scenarios.find(
      (scenario) => scenario.key === snapshots[run.key].scenarioKey,
    )?.name ?? "Custom Prompt",
  modelCount: run.modelCount,
  status: run.status,
  cost: {
    confirmed: run.confirmedCost,
    estimated: run.estimatedCost,
    unknownCount: run.unknownCostCount,
    checkStatus: run.status.ongoing
      ? "확인 중"
      : run.unknownCostCount > 0
        ? "미확인 포함"
        : run.estimatedCost !== null
          ? "추정 포함"
          : "확정",
  },
  inactiveModelCount: run.slots.filter((slot) => !choiceFor(slot)?.selectable)
    .length,
}));

export function historyDetail(key: string): HistoryDetailView | undefined {
  const run = dbMock.runs.find((run) => run.key === key);
  const input = snapshots[key];
  if (!run || !input) return;
  return {
    key,
    input:
      input.prompt === null
        ? { kind: "missing" }
        : {
            kind: "available",
            prompt: input.prompt,
            text: input.text ?? "",
            schema: input.jsonSchema,
            attachments: input.attachments,
          },
    models: run.slots.map((slot) => {
      const choice = choiceFor(slot);
      return {
        key: choice?.key ?? slot.key,
        name: slot.name,
        provider: slot.provider,
        currentState: !choice
          ? "missing"
          : choice.selectable
            ? "active"
            : "inactive",
      };
    }),
    settings: [
      {
        label: "테스트 유형",
        value: input.mode === "scenario" ? "기본 시나리오" : "Custom Prompt",
      },
      { label: "Temperature", value: input.temperature || "미기록" },
      { label: "최대 출력 토큰", value: input.maxTokens || "미기록" },
      { label: "Provider·Fallback 정책", value: input.routingPolicy },
      ...(input.rerunOf
        ? [{ label: "재실행 원본 ID", value: input.rerunOf }]
        : []),
    ],
  };
}
export function rerunSnapshot(key: string) {
  const input = snapshots[key];
  const run = dbMock.runs.find((run) => run.key === key);
  if (!run || !input?.prompt || input.attachments.length) return;
  return createDefaultValues({
    mode: input.mode,
    scenarioKey: input.scenarioKey,
    prompt: input.prompt,
    text: input.text ?? "",
    jsonSchema: input.jsonSchema,
    temperature: input.temperature,
    maxTokens: input.maxTokens,
    comparisons: createComparisons(
      run.slots.map((slot) => choiceFor(slot)?.key ?? ""),
    ),
  });
}

// 개발 예시에서만 12건 스냅샷을 검색·정렬한다. 서비스 화면은 서버가 준 순서를 유지한다.
export function selectPreviewRows(search: HistorySearch): HistoryRow[] {
  const rows = historyRows.filter((row) => {
    const input = snapshots[row.key];
    const time = Date.parse(row.requestedAt);
    const run = dbMock.runs.find((run) => run.key === row.key);
    return (
      time >= Date.parse(`${search.from}T00:00:00+09:00`) &&
      time < Date.parse(`${search.to}T00:00:00+09:00`) + DAY_MS &&
      (!search.scenario || input.scenarioKey === search.scenario) &&
      (!search.model ||
        run?.slots.some((slot) => choiceFor(slot)?.key === search.model)) &&
      (search.status === "all" || input.status === search.status) &&
      (!search.simulationId || row.key === search.simulationId)
    );
  });
  return rows.toSorted((a, b) => {
    let result: number;
    switch (search.sort) {
      case "requestedAt":
        result = a.requestedAt.localeCompare(b.requestedAt);
        break;
      case "id":
        result = a.key.localeCompare(b.key);
        break;
      case "scenario":
        result = a.scenario.localeCompare(b.scenario);
        break;
      case "modelCount":
        result = a.modelCount - b.modelCount;
        break;
      case "status":
        result = a.status.label.localeCompare(b.status.label);
        break;
      case "costStatus":
        result = a.cost.checkStatus.localeCompare(b.cost.checkStatus);
        break;
    }
    return (
      (result || a.key.localeCompare(b.key)) *
      (search.direction === "asc" ? 1 : -1)
    );
  });
}
