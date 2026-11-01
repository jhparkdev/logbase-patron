import { createFileRoute } from "@tanstack/react-router";
import { useDeferredValue, useState } from "react";
import plusIcon from "../../assets/plus.svg";
import { modelListOptions } from "../../features/models/api/models";
import { ModelDetailPanel } from "../../features/models/components/ModelDetailPanel";
import { ModelFilters } from "../../features/models/components/ModelFilters";
import { ModelRegisterPanel } from "../../features/models/components/ModelRegisterPanel";
import { ModelTable } from "../../features/models/components/ModelTable";
import { modelsSearchSchema } from "../../features/models/lib/search";
import { Button } from "../../shared/components/ui/Button";
import { PageHeader } from "../../shared/components/ui/PageHeader";

export const Route = createFileRoute("/_app/models")({
  validateSearch: modelsSearchSchema,
  // 조건이 바뀔 때마다 loader 재실행
  loaderDeps: ({ search }) => search,
  // 화면 틀을 먼저 그리도록 대기하지 않음. 실패는 표 블록이 처리하므로 여기서 중단하지 않음
  loader: ({ context: { queryClient }, deps }) => {
    void queryClient.prefetchQuery(modelListOptions(deps));
  },
  component: ModelsPage,
});

function ModelsPage() {
  const search = Route.useSearch();
  const navigate = Route.useNavigate();
  // 재조회 중에는 이전 결과를 유지하고, 새 결과가 오면 교체
  const shown = useDeferredValue(search);
  const [registering, setRegistering] = useState(false);

  return (
    <>
      <div className="flex items-end justify-between gap-6">
        <PageHeader
          title="AI 모델 관리"
          description="사용 가능한 AI 모델을 등록하고 관리할 수 있어요. 등록된 모델은 시뮬레이터에서 사용할 수 있으며, ACTIVE 상태의 모델만 고를 수 있어요."
        />
        <Button icon={plusIcon} onClick={() => setRegistering(true)}>
          신규 모델 등록
        </Button>
      </div>
      <ModelFilters
        search={search}
        // 조건이 바뀌면 1페이지로 복귀
        onChange={(filters) =>
          navigate({
            search: (prev) => ({ ...prev, ...filters, page: undefined }),
          })
        }
      />
      <ModelTable search={shown} refreshing={shown !== search} />
      {registering && (
        <ModelRegisterPanel onClose={() => setRegistering(false)} />
      )}
      {search.model !== undefined && (
        <ModelDetailPanel
          modelId={search.model}
          onClose={() =>
            navigate({ search: (prev) => ({ ...prev, model: undefined }) })
          }
        />
      )}
    </>
  );
}
