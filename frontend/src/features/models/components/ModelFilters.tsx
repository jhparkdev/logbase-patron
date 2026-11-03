import { useQuery } from "@tanstack/react-query";
import { SearchField } from "../../../shared/components/ui/SearchField";
import { Select } from "../../../shared/components/ui/Select";
import { modelProvidersQuery } from "../api/models";
import type { ModelsSearch } from "../lib/search";
import { providerOptions, STATUS_OPTIONS, statusOfOption } from "../lib/view";

type ModelFiltersProps = {
  search: ModelsSearch;
  /** 바뀐 조건만 넘김. undefined는 조건 해제 */
  onChange: (filters: Pick<ModelsSearch, "q" | "provider" | "status">) => void;
};

/** 검색어·제공사·상태 조건. 고르는 즉시 적용 */
export function ModelFilters({ search, onChange }: ModelFiltersProps) {
  // 제공사를 못 불러와도 표는 그대로 쓸 수 있어 오류 표시 없이 전체만 둠
  const providers = useQuery(modelProvidersQuery);
  return (
    <div className="flex flex-wrap gap-3 rounded-2xl bg-white p-4">
      <SearchField
        label="모델 검색"
        placeholder="모델명 또는 Model ID로 검색하세요"
        value={search.q}
        onSearch={(text) => onChange({ q: text || undefined })}
      />
      <Select
        label="Provider"
        value={search.provider ?? ""}
        options={providerOptions(providers.data?.items ?? [], search.provider)}
        onChange={(value) => onChange({ provider: value || undefined })}
        disabled={providers.data === undefined}
        className="w-56"
      />
      <Select
        label="상태"
        value={search.status ?? ""}
        options={STATUS_OPTIONS}
        onChange={(value) => onChange({ status: statusOfOption(value) })}
        className="w-56"
      />
    </div>
  );
}
