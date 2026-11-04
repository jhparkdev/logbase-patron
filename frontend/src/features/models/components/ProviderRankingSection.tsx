import { useState } from "react";
import { Badge } from "../../../shared/components/ui/Badge";
import { DataBlock } from "../../../shared/components/ui/DataBlock";
import { Result } from "../../../shared/components/ui/Result";
import { Select } from "../../../shared/components/ui/Select";
import { Skeleton } from "../../../shared/components/ui/Skeleton";
import { useProviderRanking } from "../hooks/useProviderRanking";
import {
  assumptionText,
  CACHE_CHOICES,
  DEFAULT_CACHE_CHOICE,
} from "../lib/ranking";

/** 모델의 서버 업체를 예상 총비용이 싼 순서로 보여 주는 구역. 캐시 가정을 바꾸면 다시 계산한다 */
export function ProviderRankingSection({ modelId }: { modelId: number }) {
  const [cacheChoice, setCacheChoice] = useState(DEFAULT_CACHE_CHOICE);
  return (
    <div className="flex flex-col gap-3">
      <p className="text-label text-grey-600">{assumptionText()}</p>
      <Select
        label="캐시 가정"
        labelPosition="side"
        value={cacheChoice}
        options={CACHE_CHOICES}
        onChange={setCacheChoice}
        className="w-64"
      />
      <DataBlock
        fallback={<Skeleton className="h-24" />}
        errorTitle="추천 업체를 불러오지 못했어요"
        resetKey={`${modelId}-${cacheChoice}`}
      >
        <RankingList modelId={modelId} cacheChoice={cacheChoice} />
      </DataBlock>
    </div>
  );
}

function RankingList({
  modelId,
  cacheChoice,
}: {
  modelId: number;
  cacheChoice: string;
}) {
  const { rows, excluded } = useProviderRanking(modelId, cacheChoice);
  return (
    <>
      {rows.length === 0 ? (
        <Result title="비교할 수 있는 업체가 없어요" />
      ) : (
        <ol className="flex flex-col gap-2">
          {rows.map((row, index) => (
            <li
              key={row.name}
              className="flex items-center gap-3 rounded-xl border border-grey-100 px-4 py-3"
            >
              <span className="w-5 text-label text-grey-600 tabular-nums">
                {index + 1}
              </span>
              <span className="font-semibold">{row.name}</span>
              {row.cheapest && <Badge tone="green">가장 저렴</Badge>}
              {row.caching && <Badge tone="blue">캐시 지원</Badge>}
              <span className="ml-auto tabular-nums">
                {row.cost}
                <span className="ml-1 text-label text-grey-600">USD</span>
              </span>
            </li>
          ))}
        </ol>
      )}
      {excluded && <p className="text-label text-grey-600">{excluded}</p>}
    </>
  );
}
