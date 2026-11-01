import { useSuspenseQuery } from "@tanstack/react-query";
import { lazy, Suspense } from "react";
import { RefreshingBar } from "../../../shared/components/ui/RefreshingBar";
import { Result } from "../../../shared/components/ui/Result";
import { SectionCard } from "../../../shared/components/ui/SectionCard";
import { Skeleton } from "../../../shared/components/ui/Skeleton";
import { formatCount, formatUsd } from "../../../shared/lib/format";
import { usageTrendQuery } from "../api/usage";
import type { CustomerUsageSearch } from "../lib/search";
import { type TrendPointView, trendPoint } from "../lib/view";
import { DataBlock } from "./DataBlock";

const TITLE = "사용량·비용 추이";

// 그래프 라이브러리가 커서, 이 블록을 그릴 때만 불러와 화면 틀이 늦어지지 않게 한다.
const UsageTrendCharts = lazy(() =>
  import("./UsageTrendCharts").then((module) => ({
    default: module.UsageTrendCharts,
  })),
);

const LOADING_SHAPE = (
  <div className="px-6 pb-6">
    <Skeleton className="h-64" />
  </div>
);

type UsageTrendCardProps = {
  search: CustomerUsageSearch;
  refreshing: boolean;
};

/** 일별 작업 건수와 확정·추정 비용. 단위가 달라 날짜를 맞춘 그래프 두 개로 나눈다. */
export function UsageTrendCard({ search, refreshing }: UsageTrendCardProps) {
  return (
    <SectionCard title={TITLE}>
      {refreshing && <RefreshingBar />}
      <DataBlock
        fallback={LOADING_SHAPE}
        errorTitle="사용량·비용 추이를 불러오지 못했어요"
        resetKey={JSON.stringify(usageTrendQuery(search).queryKey)}
      >
        <TrendContent search={search} />
      </DataBlock>
    </SectionCard>
  );
}

function TrendContent({ search }: { search: CustomerUsageSearch }) {
  const { data } = useSuspenseQuery(usageTrendQuery(search));
  if (data.items.every((point) => point.call_count === 0)) {
    return (
      <Result
        title="이 조건에는 API 호출 내역이 없어요"
        description="조회 조건을 바꿔 보세요."
      />
    );
  }
  const points = data.items.map(trendPoint);
  return (
    <div className="flex flex-col gap-4 px-6 pb-6">
      <TrendTable points={points} />
      <Suspense fallback={<Skeleton className="h-64" />}>
        <UsageTrendCharts points={points} />
      </Suspense>
    </div>
  );
}

/** 추정 색의 대비가 낮고 그래프는 화면 낭독기가 읽지 못해, 같은 값을 표로도 둔다. */
function TrendTable({ points }: { points: TrendPointView[] }) {
  return (
    <table className="sr-only">
      <caption>{TITLE}</caption>
      <thead>
        <tr>
          <th scope="col">날짜</th>
          <th scope="col">작업 건수</th>
          <th scope="col">확정 비용 (USD)</th>
          <th scope="col">추정 비용 (USD)</th>
          <th scope="col">비용 미확인 건수</th>
        </tr>
      </thead>
      <tbody>
        {points.map((point) => (
          <tr key={point.date}>
            <th scope="row">{point.date}</th>
            <td>{formatCount(point.tasks)}</td>
            <td>{formatUsd(point.confirmedText, "summary")}</td>
            <td>{formatUsd(point.estimatedText, "summary")}</td>
            <td>{formatCount(point.unknownCount)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
