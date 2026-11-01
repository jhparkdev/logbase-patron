// 화면 전용 표시 props다. API 응답에서 바꾸는 일은 view.ts가 한다.
export type HistoryOption = { key: string; name: string };
export type HistoryRow = {
  key: string;
  requestedAt: string;
  scenario: string;
  modelCount: number;
  status: { label: string; tone: "green" | "red" | "yellow" | "grey" };
  // 서버가 합계를 주지 않으므로 확정과 추정을 나눠 둔다. 화면에서 더하지 않는다.
  cost: {
    confirmed: string | null;
    estimated: string | null;
    unknownCount: number;
    checking: boolean;
  };
  inactiveModelCount: number | null;
};
export type HistoryListView =
  | { kind: "unavailable" | "loading" | "error" }
  | {
      kind: "ready";
      items: readonly HistoryRow[];
      total: number;
      refreshing?: boolean;
    };
export type HistoryDetailView = {
  key: string;
  input:
    | { kind: "missing" }
    | {
        kind: "available";
        prompt: string;
        text: string;
        schema: string;
        attachments: readonly {
          key: string;
          name: string;
          available: boolean;
        }[];
      };
  settings: readonly { label: string; value: string }[];
  models: readonly {
    key: string;
    name: string;
    provider: string;
    currentState: "active" | "inactive" | "missing" | "unknown";
  }[];
};
export type HistoryDetailState =
  | { kind: "unavailable" | "loading" | "error" | "missing" }
  | { kind: "ready"; value: HistoryDetailView };
