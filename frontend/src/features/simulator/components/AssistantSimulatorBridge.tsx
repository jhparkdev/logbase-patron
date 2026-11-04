import { useEffect } from "react";
import type { UseFormReturn } from "react-hook-form";
import { useAssistantBridge } from "../../../shared/lib/assistant";
import {
  applyAssistantPatch,
  assistantPatchIssue,
  simulatorAssistantState,
  simulatorRevision,
} from "../lib/assistant";
import type { SimulatorDraft, SimulatorFormValues } from "../lib/form";
import type { ModelChoice, ScenarioChoice } from "../lib/presentation";

export function AssistantSimulatorBridge({
  form,
  choices,
  scenarios,
  busy,
  onApplied,
}: {
  form: UseFormReturn<SimulatorFormValues, unknown, SimulatorDraft>;
  choices: ModelChoice[];
  scenarios: ScenarioChoice[];
  busy: boolean;
  onApplied: (value: boolean) => void;
}) {
  const bridge = useAssistantBridge();
  const { getValues, setValue } = form;
  useEffect(() => {
    if (!bridge) return;
    const update = (
      next: SimulatorFormValues,
      previous: SimulatorFormValues,
    ) => {
      for (const key of Object.keys(next) as (keyof SimulatorFormValues)[]) {
        if (next[key] !== previous[key])
          setValue(key, next[key], { shouldDirty: true });
      }
    };
    let undo: { before: SimulatorFormValues; after: string } | undefined;
    return bridge.register({
      read: () => {
        const values = getValues();
        return {
          state: simulatorAssistantState(values),
          revision: simulatorRevision(values),
        };
      },
      apply: (patch, revision) => {
        if (busy) return "비교 실행 또는 확인 중에는 설정을 바꿀 수 없어요.";
        const before = getValues();
        if (revision !== simulatorRevision(before))
          return "요청 후 입력값이 바뀌어 설정을 적용하지 않았어요. 다시 요청해 주세요.";
        const next = applyAssistantPatch(before, patch);
        const issue = assistantPatchIssue(next, choices, scenarios);
        if (issue) return issue;
        undo = { before, after: simulatorRevision(next) };
        update(next, before);
        onApplied(true);
        return undefined;
      },
      undo: () => {
        if (busy) return "실행 또는 확인 중에는 설정을 바꿀 수 없어요.";
        if (!undo || simulatorRevision(getValues()) !== undo.after)
          return "설정이 다시 변경되어 되돌릴 수 없어요.";
        update(undo.before, getValues());
        undo = undefined;
        return undefined;
      },
    });
  }, [bridge, getValues, setValue, choices, scenarios, busy, onApplied]);
  return null;
}
