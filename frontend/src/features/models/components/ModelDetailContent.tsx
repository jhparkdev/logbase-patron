import type { ReactNode } from "react";
import { Badge } from "../../../shared/components/ui/Badge";
import { formatCount, formatKstDateTime } from "../../../shared/lib/format";
import type { ModelDetail } from "../api/models";
import { modalitiesLabel, statusBadge } from "../lib/view";
import { LastTestCell, PriceCell } from "./ModelCells";

export const SECTION_TITLES = {
  basic: "기본 정보",
  price: "토큰 단가 (USD/1M)",
  test: "연결 테스트",
  status: "운영 상태 관리",
} as const;

// 값이 없을 때 빈칸 대신 보여 주는 글자
const NONE_LABEL = "없음";
const NO_PURPOSE_LABEL = "미입력";
const UNKNOWN_LABEL = "미확인";

const supportLabel = (supported: boolean) => (supported ? "지원" : "미지원");
const timeOrNone = (utc: string | null) =>
  utc === null ? NONE_LABEL : formatKstDateTime(utc);

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="flex flex-col gap-3">
      <h3 className="font-bold">{title}</h3>
      <dl className="grid grid-cols-[8.5rem_1fr] items-center gap-x-4 gap-y-2.5 text-body-sm">
        {children}
      </dl>
    </section>
  );
}

function Row({ label, children }: { label: string; children: ReactNode }) {
  return (
    <>
      <dt className="text-grey-600">{label}</dt>
      <dd className="tabular-nums">{children}</dd>
    </>
  );
}

/** 모델 상세 내용. 조회 전용이고 수정·테스트·상태 변경은 이후 단계에서 붙임 */
export function ModelDetailContent({ model }: { model: ModelDetail }) {
  const price = model.current_price;
  const status = statusBadge(model.status);
  return (
    <div className="flex flex-col gap-8">
      <Section title={SECTION_TITLES.basic}>
        <Row label="표시 이름">{model.display_name}</Row>
        <Row label="Model ID">{model.openrouter_model_id}</Row>
        <Row label="Provider">{model.provider}</Row>
        <Row label="용도">{model.purpose ?? NO_PURPOSE_LABEL}</Row>
        <Row label="입력 형식">{modalitiesLabel(model.input_modalities)}</Row>
        <Row label="출력 형식">{modalitiesLabel(model.output_modalities)}</Row>
        <Row label="JSON 스키마">
          {supportLabel(model.supports_json_schema)}
        </Row>
        <Row label="함수 호출">{supportLabel(model.supports_tools)}</Row>
        <Row label="Context Length">
          {model.context_length === null
            ? UNKNOWN_LABEL
            : formatCount(model.context_length)}
        </Row>
      </Section>
      <Section title={SECTION_TITLES.price}>
        <Row label="Input">
          <PriceCell perToken={price?.input_price_per_token} />
        </Row>
        <Row label="Output">
          <PriceCell perToken={price?.output_price_per_token} />
        </Row>
        <Row label="가격 확인 시각">
          {timeOrNone(price?.checked_at ?? null)}
        </Row>
      </Section>
      <Section title={SECTION_TITLES.test}>
        <Row label="마지막 테스트">
          <LastTestCell row={model} />
        </Row>
        <Row label="마지막 성공 테스트">
          {timeOrNone(model.last_success_test_at)}
        </Row>
      </Section>
      <Section title={SECTION_TITLES.status}>
        <Row label="현재 상태">
          <Badge tone={status.tone}>{status.label}</Badge>
        </Row>
        <Row label="활성화 시각">{timeOrNone(model.activated_at)}</Row>
        <Row label="비활성화 시각">{timeOrNone(model.deactivated_at)}</Row>
      </Section>
    </div>
  );
}
