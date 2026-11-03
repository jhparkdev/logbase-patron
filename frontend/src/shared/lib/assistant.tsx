import { createContext, type ReactNode, useContext, useState } from "react";
import type { components } from "../api/schema";

type Schemas = components["schemas"];
export type AssistantPatch = Schemas["SimulatorPatch"];
export type SimulatorSnapshot = {
  state: Schemas["SimulatorState"];
  revision: string;
};
export type SimulatorBridge = {
  read: () => SimulatorSnapshot;
  apply: (patch: AssistantPatch, revision: string) => string | undefined;
  undo: () => string | undefined;
};

export function createAssistantBridge() {
  let current: SimulatorBridge | null = null;
  const listeners = new Set<() => void>();
  const emit = () => {
    for (const listener of listeners) listener();
  };
  return {
    getSnapshot: () => current,
    subscribe: (listener: () => void) => {
      listeners.add(listener);
      return () => {
        listeners.delete(listener);
      };
    },
    register: (value: SimulatorBridge) => {
      current = value;
      emit();
      return () => {
        if (current === value) {
          current = null;
          emit();
        }
      };
    },
  };
}

const AssistantContext = createContext<ReturnType<
  typeof createAssistantBridge
> | null>(null);

export function AssistantProvider({ children }: { children: ReactNode }) {
  const [bridge] = useState(createAssistantBridge);
  return <AssistantContext value={bridge}>{children}</AssistantContext>;
}

export function useAssistantBridge() {
  return useContext(AssistantContext);
}
