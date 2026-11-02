import type { ReactNode } from "react";
import {
  type Column,
  DataTable,
} from "../../../shared/components/ui/DataTable";

type PendingTableProps = {
  caption: string;
  /** 칸 내용(render)은 목록 API의 생성 타입이 생기면 채운다. */
  columns: Omit<Column<never>, "render" | "sortable">[];
  empty: ReactNode;
};

/**
 * 목록 API가 생기기 전의 표. 머리글과 빈 상태만 보여 준다.
 * API를 연결하면 행 타입과 칸 내용을 정해 DataTable로 바꾼다.
 */
export function PendingTable({ caption, columns, empty }: PendingTableProps) {
  return (
    <DataTable
      caption={caption}
      columns={columns.map((column) => ({
        ...column,
        sortable: false,
        render: () => null,
      }))}
      rows={[]}
      rowKey={() => ""}
      empty={empty}
    />
  );
}
