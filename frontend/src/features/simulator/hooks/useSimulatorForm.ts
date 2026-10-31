import { zodResolver } from "@hookform/resolvers/zod";
import { useRef, useState } from "react";
import { useForm, useWatch } from "react-hook-form";
import {
  createDefaultValues,
  type SimulatorDraft,
  type SimulatorFormValues,
  simulatorSchemaFor,
} from "../lib/form";
import { MODEL_LIMITS } from "../lib/limits";
import {
  type ModelChoice,
  type ScenarioChoice,
  selectionIssues,
} from "../lib/presentation";

export function useSimulatorForm({
  choices,
  scenarios,
  onRun,
  running,
  initialValues,
}: {
  choices: ModelChoice[];
  scenarios: ScenarioChoice[];
  onRun?: (draft: SimulatorDraft) => void | Promise<void>;
  running: boolean;
  initialValues?: Partial<SimulatorFormValues>;
}) {
  const form = useForm<SimulatorFormValues, unknown, SimulatorDraft>({
    resolver: zodResolver(simulatorSchemaFor(choices)),
    defaultValues: createDefaultValues(initialValues),
    mode: "onSubmit",
    reValidateMode: "onSubmit",
    shouldUnregister: false,
    shouldFocusError: false,
  });
  const [advancedOpen, setAdvancedOpen] = useState(false);
  const [pendingDraft, setPendingDraft] = useState<SimulatorDraft>();
  const [submitting, setSubmitting] = useState(false);
  const [issues, setIssues] = useState<string[]>([]);
  const sending = useRef(false);
  const [comparisons, mode, scenarioKey] = useWatch({
    control: form.control,
    name: ["comparisons", "mode", "scenarioKey"],
  });
  const count = comparisons.filter((item) => item.modelKey).length;
  const busy = submitting || running;
  const selectedScenario =
    mode === "scenario"
      ? scenarios.find((item) => item.key === scenarioKey)
      : undefined;
  const submit = form.handleSubmit(
    (draft) => {
      if (busy || !onRun) return;
      const nextIssues = selectionIssues(draft, choices, scenarios);
      setIssues(nextIssues);
      if (!nextIssues.length) setPendingDraft(draft);
    },
    (errors) => {
      setIssues([]);
      if (errors.temperature || errors.maxTokens || errors.reasoningEffort)
        setAdvancedOpen(true);
      else if (errors.prompt) form.setFocus("prompt");
      else if (errors.jsonSchema) form.setFocus("jsonSchema");
    },
  );
  const confirm = async () => {
    if (!pendingDraft || !onRun || busy || sending.current) return;
    const nextIssues = selectionIssues(pendingDraft, choices, scenarios);
    setIssues(nextIssues);
    if (nextIssues.length) {
      setPendingDraft(undefined);
      return;
    }
    sending.current = true;
    setSubmitting(true);
    setPendingDraft(undefined);
    try {
      await onRun(pendingDraft);
    } catch {
      setIssues([
        "실행 요청을 보내지 못했습니다. 잠시 후 다시 시도하시기 바랍니다.",
      ]);
    } finally {
      sending.current = false;
      setSubmitting(false);
    }
  };
  return {
    form,
    advancedOpen,
    setAdvancedOpen,
    pendingDraft,
    setPendingDraft,
    busy,
    submitting,
    issues,
    selectedScenario,
    submit,
    confirm,
    canRun:
      !!onRun &&
      !busy &&
      count >= MODEL_LIMITS.min &&
      count <= MODEL_LIMITS.max,
  };
}
