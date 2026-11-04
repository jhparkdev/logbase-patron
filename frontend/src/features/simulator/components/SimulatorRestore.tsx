import { Link } from "@tanstack/react-router";
import { Button } from "../../../shared/components/ui/Button";
import { Notice } from "../../../shared/components/ui/Notice";
import { PageHeader } from "../../../shared/components/ui/PageHeader";
import { Result } from "../../../shared/components/ui/Result";
import { Skeleton } from "../../../shared/components/ui/Skeleton";
import type { ModelFavoritesView } from "../lib/favorites";
import { restoreRerunValues } from "../lib/rerun";
import type { SimulatorRestoreView } from "../lib/rerun-draft";
import { SimulatorPage, type SimulatorPageProps } from "./SimulatorPage";

const RESTORE_TITLES = {
  unavailable: "재실행 조건 불러오기를 준비하고 있어요",
  missing: "재실행할 입력을 찾을 수 없어요",
  error: "재실행 조건을 불러오지 못했어요",
};
const RESTORE_DESCRIPTIONS = {
  unavailable:
    "API가 연결되면 과거 입력과 현재 모델 정보를 확인해 복원할 수 있어요.",
  missing: "원래 이력을 확인하거나 잠시 후 다시 시도해 주세요.",
  error: "원래 이력을 확인하거나 잠시 후 다시 시도해 주세요.",
};

export function SimulatorRestore({
  sourceKey,
  view = { kind: "unavailable" },
  onRetry,
  favorites,
  page,
}: {
  sourceKey: string;
  view?: SimulatorRestoreView;
  onRetry?: () => void;
  favorites?: ModelFavoritesView;
  page?: Omit<SimulatorPageProps, "choices" | "scenarios" | "initialValues">;
}) {
  if (view.kind !== "ready" || view.key !== sourceKey)
    return (
      <>
        <PageHeader title="AI 모델 시뮬레이터" />
        {view.kind === "loading" || view.kind === "ready" ? (
          <>
            <p role="status">재실행 조건을 불러오고 있어요</p>
            <Skeleton className="h-48 w-full" />
          </>
        ) : (
          <Result
            title={RESTORE_TITLES[view.kind]}
            description={RESTORE_DESCRIPTIONS[view.kind]}
            action={
              view.kind === "error" && onRetry ? (
                <Button variant="secondary" onClick={onRetry}>
                  다시 시도
                </Button>
              ) : undefined
            }
          />
        )}
        <Link
          to="/simulator"
          search={{ sort: "model", direction: "asc" }}
          className="text-body-sm font-semibold text-blue-600 underline"
        >
          새 조건으로 준비하기
        </Link>
      </>
    );
  const restored = restoreRerunValues(
    view.values,
    view.choices,
    view.scenarios,
  );
  return (
    <>
      <Notice
        title="과거 실행 조건을 불러왔어요"
        description="입력과 모델을 확인한 뒤 새 비교를 실행해 주세요. 원래 실행 결과는 바뀌지 않아요."
      />
      {restored.warnings.length > 0 && (
        <ul
          role="status"
          className="space-y-1 rounded-xl bg-warning-weak p-4 text-body-sm text-yellow-900"
        >
          {restored.warnings.map((warning) => (
            <li key={warning}>{warning}</li>
          ))}
        </ul>
      )}
      <SimulatorPage
        {...page}
        key={sourceKey}
        initialValues={restored.values}
        choices={view.choices}
        scenarios={view.scenarios}
        favorites={favorites}
      />
    </>
  );
}
