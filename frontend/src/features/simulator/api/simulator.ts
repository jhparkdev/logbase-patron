import { queryOptions } from "@tanstack/react-query";
import { api, unwrap } from "../../../shared/api/client";
import type { components } from "../../../shared/api/schema";

type Schemas = components["schemas"];

const ROOT_KEY = "simulator";
/** 활성 모델은 관리 화면에서만 바뀌므로 잠시 캐시 */
const CATALOG_STALE_TIME_MS = 60_000;
/** 서버도 업체 목록을 10분 보관한다. 같은 값을 다시 묻지 않는다. */
const PROVIDERS_STALE_TIME_MS = 5 * 60_000;
/** 이미지 한도는 배포할 때만 바뀐다. */
const LIMITS_STALE_TIME_MS = 60 * 60_000;
/** 시나리오는 운영 명령으로만 바뀐다. */
const SCENARIOS_STALE_TIME_MS = 5 * 60_000;
/** 진행 중인 실행을 다시 읽는 간격. 백엔드 진행 조회 계약의 5초와 같다. */
const RUN_POLL_INTERVAL_MS = 5_000;
/** 모델 목록 API의 한 페이지 최대 크기 */
const MODEL_PAGE_SIZE = 100;

function isOngoing(status: Schemas["SimulationStatus"]) {
  return status === "PENDING" || status === "RUNNING";
}

/** 비교 실행에서 고를 수 있는 활성 모델 */
export const activeModelsQuery = queryOptions({
  queryKey: [ROOT_KEY, "models"],
  queryFn: async () =>
    unwrap(
      await api.GET("/api/models", {
        params: {
          query: {
            status: ["ACTIVE"],
            sort: "display_name",
            order: "asc",
            page_size: MODEL_PAGE_SIZE,
          },
        },
      }),
    ),
  staleTime: CATALOG_STALE_TIME_MS,
  retry: false,
});

/** 새 실행은 활성 시나리오만 고른다. 재실행은 지금 비활성인 원본도 찾아야 한다. */
export function scenariosOptions(includeInactive: boolean) {
  return queryOptions({
    queryKey: [ROOT_KEY, "scenarios", includeInactive],
    queryFn: async () =>
      unwrap(
        await api.GET("/api/scenarios", {
          params: { query: { include_inactive: includeInactive } },
        }),
      ),
    staleTime: SCENARIOS_STALE_TIME_MS,
    retry: false,
  });
}

export function executionProvidersOptions(modelId: number) {
  return queryOptions({
    queryKey: [ROOT_KEY, "execution-providers", modelId],
    queryFn: async () =>
      unwrap(
        await api.GET("/api/models/{model_id}/execution-providers", {
          params: { path: { model_id: modelId } },
        }),
      ),
    staleTime: PROVIDERS_STALE_TIME_MS,
    retry: false,
  });
}

export const imageLimitsQuery = queryOptions({
  queryKey: [ROOT_KEY, "image-limits"],
  queryFn: async () => unwrap(await api.GET("/api/simulations/images/limits")),
  staleTime: LIMITS_STALE_TIME_MS,
  retry: false,
});

export function runKey(simulationId: string) {
  return [ROOT_KEY, "run", simulationId];
}

/** 진행·결과 조회. 끝나지 않은 실행만 폴링 */
export function runOptions(simulationId: string) {
  return queryOptions({
    queryKey: runKey(simulationId),
    queryFn: async () =>
      unwrap(
        await api.GET("/api/simulations/{simulation_id}", {
          params: { path: { simulation_id: simulationId } },
        }),
      ),
    retry: false,
    refetchInterval: (query) => {
      const status = query.state.data?.summary.status;
      return status && isOngoing(status) ? RUN_POLL_INTERVAL_MS : false;
    },
  });
}

/** 재실행 초안. 읽기만 하며 실행은 사용자가 새 비교를 보낼 때 시작한다. */
export function rerunDraftOptions(simulationId: string) {
  return queryOptions({
    queryKey: [ROOT_KEY, "rerun-draft", simulationId],
    queryFn: async () =>
      unwrap(
        await api.GET("/api/simulations/{simulation_id}/rerun-draft", {
          params: { path: { simulation_id: simulationId } },
        }),
      ),
    retry: false,
  });
}

/**
 * 이미지 한 장을 올린다. 생성 타입은 파일을 string으로 적어 File을 그대로 넣을 수 없어,
 * 본문은 비워 두고 직렬화 단계에서 실제 FormData를 보낸다.
 */
export async function uploadImage(file: File) {
  const form = new FormData();
  form.append("file", file);
  return unwrap(
    await api.POST("/api/simulations/images", {
      body: { file: "" },
      bodySerializer: () => form,
    }),
  );
}

/** 비교 실행 접수. 모델 호출 비용이 발생할 수 있다. */
export async function createSimulation(
  body: Schemas["SimulationCreateRequest"],
) {
  return unwrap(await api.POST("/api/simulations", { body }));
}

export async function cancelRun(simulationId: string) {
  return unwrap(
    await api.POST("/api/simulations/{simulation_id}/cancel", {
      params: { path: { simulation_id: simulationId } },
    }),
  );
}

export async function cancelSlot(simulationId: string, slotNo: number) {
  return unwrap(
    await api.POST("/api/simulations/{simulation_id}/slots/{slot_no}/cancel", {
      params: { path: { simulation_id: simulationId, slot_no: slotNo } },
    }),
  );
}
