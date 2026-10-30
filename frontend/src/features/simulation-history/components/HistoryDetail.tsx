import type { ReactNode } from "react";
import { Badge } from "../../../shared/components/ui/Badge";
import { Button } from "../../../shared/components/ui/Button";
import { Dialog } from "../../../shared/components/ui/Dialog";
import { Result } from "../../../shared/components/ui/Result";
import { Skeleton } from "../../../shared/components/ui/Skeleton";
import type { HistoryDetailState } from "../lib/presentation";
import { rerunBlockReason } from "../lib/rerun";

const modelStates = {
  active: "활성",
  inactive: "비활성",
  missing: "현재 목록 없음",
  unknown: "확인 전",
};
export function HistoryDetail({
  selected,
  open,
  state,
  onClose,
  onRetry,
  onRerun,
  renderResults,
}: {
  selected?: string;
  open: boolean;
  state: HistoryDetailState;
  onClose: () => void;
  onRetry?: () => void;
  onRerun?: (key: string) => void;
  renderResults?: (key: string) => ReactNode;
}) {
  const detail =
    state.kind === "ready" && state.value.key === selected
      ? state.value
      : undefined;
  const reason = detail ? rerunBlockReason(detail) : undefined;
  return (
    <Dialog
      open={open}
      title="시뮬레이션 실행 상세"
      onClose={onClose}
      showTopClose
      action={
        detail && (
          <Button
            variant="secondary"
            disabled={!!reason || !onRerun}
            onClick={() => onRerun?.(detail.key)}
          >
            이 조건으로 다시 준비
          </Button>
        )
      }
    >
      {detail ? (
        <div className="flex flex-col gap-5">
          <p className="break-all text-body-sm text-grey-600">
            Simulation ID · {detail.key}
          </p>
          <section
            aria-label="당시 입력과 설정"
            className="rounded-xl bg-grey-50 p-4"
          >
            <h3 className="mb-3 font-semibold">당시 입력과 설정</h3>
            {detail.input.kind === "available" ? (
              <dl className="space-y-4 text-body-sm">
                <div>
                  <dt className="font-semibold">Prompt</dt>
                  <dd className="mt-1 whitespace-pre-wrap break-words">
                    {detail.input.prompt || "미기록"}
                  </dd>
                </div>
                <div>
                  <dt className="font-semibold">입력 텍스트</dt>
                  <dd className="mt-1 whitespace-pre-wrap break-words">
                    {detail.input.text || "미사용"}
                  </dd>
                </div>
                <div>
                  <dt className="font-semibold">JSON Schema</dt>
                  <dd className="mt-1 whitespace-pre-wrap break-words">
                    {detail.input.schema || "미사용"}
                  </dd>
                </div>
                <div>
                  <dt className="font-semibold">첨부 이미지</dt>
                  <dd className="mt-1">
                    {detail.input.attachments.length ? (
                      <ul>
                        {detail.input.attachments.map((file) => (
                          <li key={file.key}>
                            {file.name}
                            {!file.available && " · 접근 불가"}
                          </li>
                        ))}
                      </ul>
                    ) : (
                      "미사용"
                    )}
                  </dd>
                </div>
              </dl>
            ) : (
              <p className="text-body-sm">저장된 입력을 확인할 수 없어요.</p>
            )}
            <dl className="mt-4 grid grid-cols-2 gap-3 border-t border-grey-200 pt-4 text-body-sm">
              {detail.settings.map((setting) => (
                <div key={setting.label}>
                  <dt className="text-grey-600">{setting.label}</dt>
                  <dd className="mt-1 whitespace-pre-wrap break-words tabular-nums">
                    {setting.value}
                  </dd>
                </div>
              ))}
            </dl>
          </section>
          <section aria-label="현재 모델 상태">
            <h3 className="mb-2 font-semibold">현재 모델 상태</h3>
            <ul className="space-y-2">
              {detail.models.map((model) => (
                <li
                  key={model.key}
                  className="flex flex-wrap items-center gap-2 text-body-sm"
                >
                  <span>
                    {model.name} · {model.provider}
                  </span>
                  <Badge
                    tone={model.currentState === "active" ? "green" : "yellow"}
                  >
                    {modelStates[model.currentState]}
                  </Badge>
                </li>
              ))}
            </ul>
            <p className="mt-2 text-caption text-grey-600">
              현재 상태는 재실행 준비에만 사용해요. 아래 과거 결과와 당시 비용은
              변경하지 않아요.
            </p>
          </section>
          {renderResults ? (
            renderResults(detail.key)
          ) : (
            <p className="text-body-sm text-grey-600">
              모델별 결과 조회를 준비하고 있어요.
            </p>
          )}
          {reason ? (
            <p
              role="status"
              className="rounded-lg bg-warning-weak p-3 text-body-sm text-yellow-900"
            >
              {reason}
            </p>
          ) : (
            <p className="text-body-sm text-grey-600">
              다시 준비를 누르면 P-04에서 입력과 모델을 검토할 수 있어요. 새
              비교를 실행할 때 비용이 발생하며 기존 기록은 유지돼요.
            </p>
          )}
          {!onRerun && (
            <p className="text-body-sm text-grey-600">
              재실행 조건을 불러오는 기능을 준비하고 있어요.
            </p>
          )}
        </div>
      ) : state.kind === "loading" || state.kind === "ready" ? (
        <div>
          <p role="status" className="mb-3">
            실행 상세를 불러오고 있어요
          </p>
          <Skeleton className="h-40 w-full" />
        </div>
      ) : (
        <Result
          title={
            state.kind === "missing"
              ? "실행 기록을 찾을 수 없어요"
              : state.kind === "error"
                ? "실행 상세를 불러오지 못했어요"
                : "상세 조회를 준비하고 있어요"
          }
          description={
            state.kind === "unavailable"
              ? "API가 연결되면 저장된 입력과 결과를 확인할 수 있어요."
              : "실행 ID를 확인하거나 잠시 후 다시 시도해 주세요."
          }
          action={
            state.kind === "error" && onRetry ? (
              <Button variant="secondary" onClick={onRetry}>
                다시 시도
              </Button>
            ) : undefined
          }
        />
      )}
    </Dialog>
  );
}
