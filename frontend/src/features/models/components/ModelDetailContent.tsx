import { type ReactNode, useState } from "react";
import { Button } from "../../../shared/components/ui/Button";
import { formatCount } from "../../../shared/lib/format";
import type { ModelDetail } from "../api/models";
import { displayNameFormSchema, purposeFormSchema } from "../lib/infoForm";
import { modalitiesLabel, timeOrNone } from "../lib/view";
import { ConnectionTestDialog } from "./ConnectionTestDialog";
import { Row, Rows } from "./DetailRows";
import { EditableInfoRow } from "./EditableInfoRow";
import { LastTestCell, PriceCell } from "./ModelCells";
import { ModelStatusControls } from "./ModelStatusControls";

export const SECTION_TITLES = {
  basic: "기본 정보",
  price: "토큰 단가 (USD/1M)",
  test: "연결 테스트",
  status: "운영 상태 관리",
} as const;

// 값을 모를 때 빈칸 대신 보여 주는 글자
const UNKNOWN_LABEL = "미확인";

const supportLabel = (supported: boolean) => (supported ? "지원" : "미지원");

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="flex flex-col gap-3">
      <h3 className="font-bold">{title}</h3>
      {children}
    </section>
  );
}

/** 모델 상세 내용. 표시 이름·용도는 연필로 수정하고, 연결 테스트는 창에서 실행. 상태 변경은 확인창을 거쳐 실행 */
export function ModelDetailContent({ model }: { model: ModelDetail }) {
  const [testing, setTesting] = useState(false);
  const price = model.current_price;
  return (
    <div className="flex flex-col gap-8">
      <Section title={SECTION_TITLES.basic}>
        <Rows>
          <EditableInfoRow
            modelId={model.model_id}
            field="display_name"
            label="표시 이름"
            value={model.display_name}
            schema={displayNameFormSchema}
          />
          <EditableInfoRow
            modelId={model.model_id}
            field="purpose"
            label="용도"
            value={model.purpose}
            schema={purposeFormSchema}
          />
          <Row label="Model ID">{model.openrouter_model_id}</Row>
          <Row label="Provider">{model.provider}</Row>
          <Row label="입력 형식">{modalitiesLabel(model.input_modalities)}</Row>
          <Row label="출력 형식">
            {modalitiesLabel(model.output_modalities)}
          </Row>
          <Row label="JSON 스키마">
            {supportLabel(model.supports_json_schema)}
          </Row>
          <Row label="함수 호출">{supportLabel(model.supports_tools)}</Row>
          <Row label="Context Length">
            {model.context_length === null
              ? UNKNOWN_LABEL
              : formatCount(model.context_length)}
          </Row>
        </Rows>
      </Section>
      <Section title={SECTION_TITLES.price}>
        <Rows>
          <Row label="Input">
            <PriceCell perToken={price?.input_price_per_token} />
          </Row>
          <Row label="Output">
            <PriceCell perToken={price?.output_price_per_token} />
          </Row>
          <Row label="가격 확인 시각">
            {timeOrNone(price?.checked_at ?? null)}
          </Row>
        </Rows>
      </Section>
      <Section title={SECTION_TITLES.test}>
        <Rows>
          <Row label="마지막 테스트">
            <LastTestCell row={model} />
          </Row>
          <Row label="마지막 성공 테스트">
            {timeOrNone(model.last_success_test_at)}
          </Row>
        </Rows>
        <div className="flex justify-end">
          <Button variant="secondary" onClick={() => setTesting(true)}>
            연결 테스트
          </Button>
        </div>
        {testing && (
          <ConnectionTestDialog
            model={model}
            onClose={() => setTesting(false)}
          />
        )}
      </Section>
      <Section title={SECTION_TITLES.status}>
        <ModelStatusControls model={model} />
      </Section>
    </div>
  );
}
