import {
  type QueryKey,
  type UseSuspenseQueryOptions,
  useSuspenseQuery,
} from "@tanstack/react-query";
import type { ReactNode } from "react";
import { DataBlock } from "../../../shared/components/ui/DataBlock";
import { DataTable } from "../../../shared/components/ui/DataTable";
import { Pagination } from "../../../shared/components/ui/Pagination";
import { RefreshingBar } from "../../../shared/components/ui/RefreshingBar";
import { SectionCard } from "../../../shared/components/ui/SectionCard";
import { TableSkeleton } from "../../../shared/components/ui/TableSkeleton";
import { useListSort } from "../hooks/useListSort";
import type { ListColumn } from "../lib/list";
import type { BudgetListView } from "../lib/search";
import { ViewAllLink } from "./ViewAllLink";

/** 불러오는 동안 보여 줄 회색 행 수 */
const LOADING_ROWS = 5;

/** 목록 API 응답의 공통 모양. 정렬과 페이지는 서버가 한다. */
type ListPage<Row> = {
  items: Row[];
  total: number;
  page: number;
  page_size: number;
};

type ListTableProps<View extends BudgetListView, Row, Key extends QueryKey> = {
  view: View;
  title: string;
  description?: string;
  /** 제목 오른쪽에 전체보기와 함께 둘 조작(예: 등록 버튼) */
  action?: ReactNode;
  errorTitle: string;
  query: UseSuspenseQueryOptions<ListPage<Row>, Error, ListPage<Row>, Key>;
  /** 칸 key는 그 표의 정렬 허용 목록 값만 쓴다. 모든 칸을 머리글로 정렬한다. */
  columns: ListColumn<View, Row>[];
  rowKey: (row: Row) => string;
  empty: ReactNode;
  refreshing: boolean;
  /** 있으면 전체보기라 아래에 페이지 이동을 두고, 없으면 요약 화면의 표다. */
  onPageChange?: (page: number) => void;
  /** 요약 화면에서만 표 아래에 붙이는 블록 */
  children?: ReactNode;
};

/**
 * 이 화면의 목록 표 하나. 요약 화면에서는 서버가 고른 미리보기를, 전체보기에서는 페이지를 나눈 전체를 보여 준다.
 * 로딩·다시 불러오기·실패는 이 블록 안에서만 처리해 다른 블록에 영향을 주지 않는다.
 */
export function ListTable<
  View extends BudgetListView,
  Row,
  Key extends QueryKey,
>({
  view,
  title,
  description,
  action,
  errorTitle,
  query,
  columns,
  rowKey,
  empty,
  refreshing,
  onPageChange,
  children,
}: ListTableProps<View, Row, Key>) {
  const fullView = onPageChange !== undefined;
  return (
    <SectionCard
      title={title}
      description={description}
      action={
        fullView && action === undefined ? undefined : (
          <div className="flex items-center gap-4">
            {!fullView && <ViewAllLink view={view} title={title} />}
            {action}
          </div>
        )
      }
    >
      {refreshing && <RefreshingBar />}
      <DataBlock
        fallback={<TableSkeleton rows={LOADING_ROWS} />}
        errorTitle={errorTitle}
        resetKey={JSON.stringify(query.queryKey)}
      >
        <ListRows
          view={view}
          title={title}
          query={query}
          columns={columns}
          rowKey={rowKey}
          empty={empty}
          onPageChange={onPageChange}
        />
      </DataBlock>
      {!fullView && children}
    </SectionCard>
  );
}

type ListRowsProps<
  View extends BudgetListView,
  Row,
  Key extends QueryKey,
> = Pick<
  ListTableProps<View, Row, Key>,
  "view" | "title" | "query" | "columns" | "rowKey" | "empty" | "onPageChange"
>;

function ListRows<View extends BudgetListView, Row, Key extends QueryKey>({
  view,
  title,
  query,
  columns,
  rowKey,
  empty,
  onPageChange,
}: ListRowsProps<View, Row, Key>) {
  const { data } = useSuspenseQuery(query);
  const { sort, onSortChange } = useListSort(view);
  return (
    <>
      <DataTable
        caption={title}
        columns={columns.map((column) => ({ ...column, sortable: true }))}
        rows={data.items}
        rowKey={rowKey}
        sort={sort}
        onSortChange={onSortChange}
        empty={empty}
      />
      {onPageChange && (
        <Pagination
          total={data.total}
          pageSize={data.page_size}
          page={data.page}
          onPageChange={onPageChange}
        />
      )}
    </>
  );
}
