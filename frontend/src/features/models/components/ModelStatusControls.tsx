import { useState } from "react";
import { Badge } from "../../../shared/components/ui/Badge";
import { Button } from "../../../shared/components/ui/Button";
import type { ModelDetail } from "../api/models";
import {
  type ChangeableStatus,
  statusBadge,
  statusChangeTargets,
  statusChangeText,
  timeOrNone,
} from "../lib/view";
import { Row, Rows } from "./DetailRows";
import { StatusChangeDialog } from "./StatusChangeDialog";

/** 현재 상태와 활성화·비활성화 시각, 상태 변경 버튼 */
export function ModelStatusControls({ model }: { model: ModelDetail }) {
  // 확인창을 연 대상 상태. 없으면 창이 닫힌 상태
  const [target, setTarget] = useState<ChangeableStatus>();
  const status = statusBadge(model.status);
  return (
    <>
      <Rows>
        <Row label="현재 상태">
          <Badge tone={status.tone}>{status.label}</Badge>
        </Row>
        <Row label="활성화 시각">{timeOrNone(model.activated_at)}</Row>
        <Row label="비활성화 시각">{timeOrNone(model.deactivated_at)}</Row>
      </Rows>
      <div className="flex justify-end gap-2">
        {statusChangeTargets(model.status).map((next) => (
          <Button
            key={next}
            variant="secondary"
            onClick={() => setTarget(next)}
          >
            {statusChangeText(next).action}
          </Button>
        ))}
      </div>
      {target && (
        <StatusChangeDialog
          model={model}
          target={target}
          onClose={() => setTarget(undefined)}
        />
      )}
    </>
  );
}
