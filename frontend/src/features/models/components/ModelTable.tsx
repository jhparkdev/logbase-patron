import { useSuspenseQuery } from "@tanstack/react-query";
import { type ReactNode, useState } from "react";
import { DataBlock } from "../../../shared/components/ui/DataBlock";
import { DataTable } from "../../../shared/components/ui/DataTable";
import { Pagination } from "../../../shared/components/ui/Pagination";
import { RefreshingBar } from "../../../shared/components/ui/RefreshingBar";
import { Result } from "../../../shared/components/ui/Result";
import { SectionCard } from "../../../shared/components/ui/SectionCard";
import { TableSkeleton } from "../../../shared/components/ui/TableSkeleton";
import { type ModelRow, modelListOptions } from "../api/models";
import { useModelPageChange, useModelSort } from "../hooks/useModelTable";
import { hasModelFilter, type ModelsSearch } from "../lib/search";
import { ConnectionTestDialog } from "./ConnectionTestDialog";
import { modelColumns } from "./ModelColumns";

const TITLE = "등록된 AI 모델";
const LOADING_ROWS = 5;
type ModelTableProps = { search: ModelsSearch; refreshing: boolean };

/** 등록된 모델 목록. 로딩·실패는 이 블록 안에서만 처리 */
export function ModelTable({ search, refreshing }: ModelTableProps) {
  return (
    <DataBlock
      fallback={
        <ModelCard>
          <TableSkeleton rows={LOADING_ROWS} />
        </ModelCard>
      }
      errorTitle="모델 목록을 불러오지 못했어요"
      resetKey={JSON.stringify(modelListOptions(search).queryKey)}
    >
      <ModelRows search={search} refreshing={refreshing} />
    </DataBlock>
  );
}

function ModelCard({
  count,
  children,
}: {
  count?: number;
  children: ReactNode;
}) {
  return (
    <SectionCard
      title={TITLE}
      count={count}
      description="모델명을 누르면 상세 정보를 볼 수 있어요."
    >
      {children}
    </SectionCard>
  );
}

// 데이터 도착 전에는 DataBlock이 스켈레톤 표시(Suspense)
function ModelRows({ search, refreshing }: ModelTableProps) {
  const { data } = useSuspenseQuery(modelListOptions(search));
  const { sort, onSortChange } = useModelSort();
  const onPageChange = useModelPageChange();
  // 테스트 창을 연 모델. 없으면 창이 닫힌 상태
  const [testing, setTesting] = useState<ModelRow>();
  return (
    // 전체 개수·페이지 정보는 서버 응답 값
    <ModelCard count={data.total}>
      {refreshing && <RefreshingBar />}
      <DataTable
        caption={TITLE}
        columns={modelColumns(setTesting)}
        rows={data.items}
        rowKey={(row) => String(row.model_id)}
        sort={sort}
        onSortChange={onSortChange}
        // 조건 있음: 조건 불일치 / 없음: 등록된 모델 없음
        empty={
          hasModelFilter(search) ? (
            <Result title="조건에 맞는 모델이 없어요" />
          ) : (
            <Result title="등록된 모델이 없어요" />
          )
        }
      />
      <Pagination
        total={data.total}
        pageSize={data.page_size}
        page={data.page}
        onPageChange={onPageChange}
      />
      {testing && (
        <ConnectionTestDialog
          model={testing}
          onClose={() => setTesting(undefined)}
        />
      )}
    </ModelCard>
  );
}
