import type { ReactNode } from "react";
import { formatKstDateTime } from "../../../shared/lib/format";
import type { ModelDetail } from "../api/models";
import { BasicInfoSection } from "./BasicInfoSection";
import { ConnectionTestSection } from "./ConnectionTestSection";
import { ModelStatusControls } from "./ModelStatusControls";
import { PriceSection, priceCheckedCaption } from "./PriceSection";
import { ProviderRankingSection } from "./ProviderRankingSection";

export const SECTION_TITLES = {
  basic: "기본 정보",
  price: "토큰 단가 (1M 토큰 기준)",
  ranking: "추천 서버 업체",
  test: "연결 테스트",
  status: "운영 상태",
} as const;

function Section({
  title,
  aside,
  children,
}: {
  title: string;
  /** 제목 오른쪽 끝. 시각 안내나 버튼 */
  aside?: ReactNode;
  children: ReactNode;
}) {
  return (
    <section className="flex flex-col gap-3">
      <div className="flex items-center justify-between gap-3">
        <h3 className="font-bold">{title}</h3>
        {aside}
      </div>
      {children}
    </section>
  );
}

/** 모델 상세 내용. 구역 다섯과 맨 아래 마지막 수정 시각 */
export function ModelDetailContent({ model }: { model: ModelDetail }) {
  return (
    <div className="flex flex-col gap-8">
      <Section title={SECTION_TITLES.basic}>
        <BasicInfoSection model={model} />
      </Section>
      <Section
        title={SECTION_TITLES.price}
        aside={
          <span className="text-caption text-grey-600 tabular-nums">
            {priceCheckedCaption(model)}
          </span>
        }
      >
        <PriceSection model={model} />
      </Section>
      <Section title={SECTION_TITLES.ranking}>
        <ProviderRankingSection modelId={model.model_id} />
      </Section>
      <ConnectionTestSection title={SECTION_TITLES.test} model={model} />
      <Section title={SECTION_TITLES.status}>
        <ModelStatusControls model={model} />
      </Section>
      <p className="text-caption text-grey-600 tabular-nums">
        마지막 수정 {formatKstDateTime(model.updated_at)}
      </p>
    </div>
  );
}
