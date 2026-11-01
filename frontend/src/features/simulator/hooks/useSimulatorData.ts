import { useQueries, useQuery, useQueryClient } from "@tanstack/react-query";
import { ApiError } from "../../../shared/api/client";
import {
  activeModelsQuery,
  cancelRun,
  cancelSlot,
  createSimulation,
  executionProvidersOptions,
  imageLimitsQuery,
  rerunDraftOptions,
  runKey,
  runOptions,
  uploadImage,
} from "../api/simulator";
import { toModelChoices } from "../lib/catalog";
import type { SimulatorDraft } from "../lib/form";
import type { ModelChoice, ResultSort, ResultsView } from "../lib/presentation";
import { toCreateRequest } from "../lib/request";
import { rerunRestoreView } from "../lib/rerun-draft";
import { sortSlots } from "../lib/result-sort";
import { toRunView } from "../lib/run-view";

function useCatalog() {
  const models = useQuery(activeModelsQuery);
  const items = models.data?.items ?? [];
  const providers = useQueries({
    queries: items.map((model) => executionProvidersOptions(model.model_id)),
  });
  const choices: ModelChoice[] = items.flatMap((model, index) => {
    const query = providers[index];
    return toModelChoices(
      model,
      query?.data
        ? {
            providers: query.data.items.map((item) => item.execution_provider),
          }
        : { failed: true },
    );
  });
  const pending = models.isPending || providers.some((q) => q.isPending);
  const catalogState: "loading" | "error" | "ready" = models.isError
    ? "error"
    : pending
      ? "loading"
      : "ready";
  return {
    choices: catalogState === "ready" ? choices : [],
    catalogState,
    onRetryCatalog: () => {
      void models.refetch();
      for (const query of providers) if (query.isError) void query.refetch();
    },
  };
}

function useRun(runId: string | undefined, sort: ResultSort) {
  const queryClient = useQueryClient();
  const run = useQuery({ ...runOptions(runId ?? ""), enabled: !!runId });
  const value = run.data && toRunView(run.data);
  const view: ResultsView = !runId
    ? { kind: "empty" }
    : value
      ? {
          kind: "ready",
          run: { ...value, slots: sortSlots(value.slots, sort) },
        }
      : run.isError
        ? { kind: "error" }
        : { kind: "loading" };
  const refresh = () => {
    if (runId)
      return queryClient.invalidateQueries({ queryKey: runKey(runId) });
  };
  return {
    view,
    onRefresh: runId ? () => void run.refetch() : undefined,
    onCancelAll: async (key: string) => {
      await cancelRun(key);
      await refresh();
    },
    // 칸 키는 run-view가 slot_no로 만든다
    onCancelSlot: async (key: string, slotKey: string) => {
      await cancelSlot(key, Number(slotKey));
      await refresh();
    },
  };
}

/** P-04가 쓰는 서버 상태와 실행 동작을 화면 값으로 묶는다. */
export function useSimulatorData({
  runId,
  sourceRun,
  sort,
  onStarted,
}: {
  runId?: string;
  sourceRun?: string;
  sort: ResultSort;
  onStarted: (simulationId: string) => void;
}) {
  const catalog = useCatalog();
  const results = useRun(runId, sort);
  const limits = useQuery(imageLimitsQuery);
  const draft = useQuery({
    ...rerunDraftOptions(sourceRun ?? ""),
    enabled: !!sourceRun,
  });
  const restore = sourceRun
    ? rerunRestoreView(
        {
          draft: draft.data,
          catalogReady: catalog.catalogState === "ready",
          error: !draft.isError
            ? null
            : draft.error instanceof ApiError && draft.error.status === 404
              ? "missing"
              : "error",
        },
        sourceRun,
        catalog.choices,
      )
    : undefined;
  return {
    ...catalog,
    results,
    restore,
    retryDraft: () => void draft.refetch(),
    imageLimits: limits.data && {
      mimeTypes: limits.data.mime_types,
      maxCount: limits.data.max_count,
      maxBytes: limits.data.max_bytes,
    },
    onRun: async (form: SimulatorDraft) => {
      // 파일을 다 올린 뒤에 실행을 접수한다. 올리다 실패하면 모델 호출 비용이 나가지 않는다.
      const uploaded = [];
      for (const file of form.files) uploaded.push(await uploadImage(file));
      const accepted = await createSimulation(
        toCreateRequest(
          form,
          uploaded.map((asset) => asset.asset_id),
          sourceRun,
        ),
      );
      onStarted(accepted.simulation_id);
    },
  };
}
