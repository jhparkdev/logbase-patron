// 화면 전용 표시 props다. HTTP 계약은 OpenAPI 준비 후 adapter에서 연결한다.
export type HistoryOption = { key: string; name: string };
export type HistoryRow = {
  key: string;
  requestedAt: string;
  scenario: string;
  modelCount: number;
  status: { label: string; tone: "green" | "red" | "yellow" | "grey" };
  cost: {
    total: string | null;
    estimated: boolean;
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
