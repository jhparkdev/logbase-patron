import { createFileRoute } from "@tanstack/react-router";
import { useDeferredValue } from "react";
import plusIcon from "../../assets/plus.svg";
import { modelListOptions } from "../../features/models/api/models";
import { ModelDetailPanel } from "../../features/models/components/ModelDetailPanel";
import { ModelTable } from "../../features/models/components/ModelTable";
import { modelsSearchSchema } from "../../features/models/lib/search";
import { Button } from "../../shared/components/ui/Button";
import { PageHeader } from "../../shared/components/ui/PageHeader";
import { SearchField } from "../../shared/components/ui/SearchField";
import { Select } from "../../shared/components/ui/Select";

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

  return (
    <>
      <div className="flex items-end justify-between gap-6">
        <PageHeader
          title="AI 모델 관리"
          description="사용 가능한 AI 모델을 등록하고 관리할 수 있어요. 등록된 모델은 시뮬레이터에서 사용할 수 있으며, ACTIVE 상태의 모델만 고를 수 있어요."
        />
        <Button icon={plusIcon} disabled>
          신규 모델 등록
        </Button>
      </div>
      <div className="flex flex-wrap gap-3 rounded-2xl bg-white p-4">
        <SearchField
          label="모델 검색"
          placeholder="모델명 또는 Model ID로 검색하세요"
          value={search.q}
          onSearch={(text) =>
            navigate({
              search: (prev) => ({
                ...prev,
                q: text || undefined,
                page: undefined,
              }),
            })
          }
        />
        <Select
          label="Provider"
          value=""
          options={[{ value: "", label: "Provider 전체" }]}
          onChange={() => {}}
          disabled
          className="w-56"
        />
        <Select
          label="상태"
          value=""
          options={[{ value: "", label: "상태 전체" }]}
          onChange={() => {}}
          disabled
          className="w-56"
        />
      </div>
      <ModelTable search={shown} refreshing={shown !== search} />
      {search.model !== undefined && (
        <ModelDetailPanel
          onClose={() =>
            navigate({ search: (prev) => ({ ...prev, model: undefined }) })
          }
        />
      )}
    </>
  );
}
