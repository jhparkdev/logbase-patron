import type { ReactNode } from "react";
import {
  type Column,
  DataTable,
} from "../../../shared/components/ui/DataTable";
import { Pagination } from "../../../shared/components/ui/Pagination";
import { PAGE_SIZE } from "../../../shared/lib/pagination";
import type { PagingControls, SortControls } from "../lib/list";

type PendingTableProps = {
  caption: string;
  /** 칸 내용(render)은 목록 API의 생성 타입이 생기면 채운다. */
  columns: Omit<Column<never>, "render" | "sortable">[];
  empty: ReactNode;
  /** 있으면 머리글로 정렬한다. */
  sorting?: SortControls;
  /** 있으면 아래에 페이지 이동을 둔다(전체보기). */
  paging?: PagingControls;
};

// 전체 건수는 목록 API 응답의 total로 바꾼다. 그 전까지의 자리값이다.
const PENDING_TOTAL = 0;

/**
 * 목록 API가 생기기 전의 표. 머리글과 빈 상태만 보여 준다.
 * API를 연결하면 행 타입과 칸 내용을 정해 DataTable로 바꾼다.
 */
export function PendingTable({
  caption,
  columns,
  empty,
  sorting,
  paging,
}: PendingTableProps) {
  return (
    <>
      <DataTable
        caption={caption}
        columns={columns.map((column) => ({
          ...column,
          sortable: sorting !== undefined,
          render: () => null,
        }))}
        rows={[]}
        rowKey={() => ""}
        sort={sorting?.sort}
        onSortChange={sorting?.onSortChange}
        empty={empty}
      />
      {paging && (
        <Pagination
          total={PENDING_TOTAL}
          pageSize={PAGE_SIZE}
          page={paging.page}
          onPageChange={paging.onPageChange}
        />
      )}
    </>
  );
}
