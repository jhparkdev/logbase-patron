import { useSuspenseQuery } from "@tanstack/react-query";
import { useState } from "react";
import { DataBlock } from "../../../shared/components/ui/DataBlock";
import { Pagination } from "../../../shared/components/ui/Pagination";
import { Result } from "../../../shared/components/ui/Result";
import { SearchField } from "../../../shared/components/ui/SearchField";
import { Skeleton } from "../../../shared/components/ui/Skeleton";
import { type OpenRouterModel, openRouterModelsQuery } from "../api/models";
import { searchTextSchema } from "../lib/search";
import { OpenRouterResult } from "./OpenRouterResult";

const LOADING_ROWS = 3;

type OpenRouterSearchProps = {
  /** 고른 모델의 Model ID */
  selectedId: string | undefined;
  onSelect: (model: OpenRouterModel) => void;
};

type SearchState = { q?: string; page: number };

/** OpenRouter 모델 검색과 결과 목록. 검색 조건은 패널 안에서만 쓰므로 주소에 두지 않음 */
export function OpenRouterSearch({
  selectedId,
  onSelect,
}: OpenRouterSearchProps) {
  const [search, setSearch] = useState<SearchState>({ page: 1 });
  return (
    <section className="flex flex-col gap-2.5">
      <h3 className="font-bold">1. OpenRouter 모델 찾기</h3>
      <SearchField
        label="OpenRouter 모델 검색"
        placeholder="모델명 또는 Model ID로 검색하세요"
        value={search.q}
        // 서버가 거절하는 검색어(100자 초과 등)는 조건으로 쓰지 않음
        onSearch={(text) => {
          const parsed = searchTextSchema.safeParse(text);
          setSearch({ q: parsed.success ? parsed.data : undefined, page: 1 });
        }}
      />
      <DataBlock
        fallback={<ResultsSkeleton />}
        errorTitle="OpenRouter 모델 목록을 불러오지 못했어요"
        resetKey={JSON.stringify(openRouterModelsQuery(search).queryKey)}
      >
        <Results
          search={search}
          selectedId={selectedId}
          onSelect={onSelect}
          onPageChange={(page) => setSearch({ ...search, page })}
        />
      </DataBlock>
    </section>
  );
}

function ResultsSkeleton() {
  return (
    <div aria-hidden="true" className="flex flex-col gap-2">
      {Array.from({ length: LOADING_ROWS }, (_, index) => (
        // 자리만 채우는 고정 개수라 순서가 바뀌지 않음
        // biome-ignore lint/suspicious/noArrayIndexKey: 고정 개수의 자리 표시
        <Skeleton key={index} className="h-20" />
      ))}
    </div>
  );
}

type ResultsProps = OpenRouterSearchProps & {
  search: SearchState;
  onPageChange: (page: number) => void;
};

function Results({ search, selectedId, onSelect, onPageChange }: ResultsProps) {
  const { data } = useSuspenseQuery(openRouterModelsQuery(search));
  if (data.items.length === 0) {
    return <Result title="조건에 맞는 모델이 없어요" />;
  }
  return (
    <>
      <div
        role="radiogroup"
        aria-label="검색 결과"
        className="flex flex-col gap-2"
      >
        {data.items.map((model) => (
          <OpenRouterResult
            key={model.openrouter_model_id}
            model={model}
            selected={model.openrouter_model_id === selectedId}
            onSelect={onSelect}
          />
        ))}
      </div>
      <Pagination
        total={data.total}
        pageSize={data.page_size}
        page={data.page}
        onPageChange={onPageChange}
      />
    </>
  );
}
