import { useState } from "react";
import { Button } from "../../../shared/components/ui/Button";
import type { ConnectionTestResult, ModelDetail } from "../api/models";
import { testResultView, timeOrNone } from "../lib/view";
import { ConnectionTestDialog } from "./ConnectionTestDialog";
import { TestStatCells } from "./TestStatCells";

const NO_TEST_LABEL = "미실행";
const NOT_RUN_HINT = "연결 테스트를 실행하면 이번 결과가 표시돼요.";
const RESULT_CLASS = { green: "text-green-700", red: "text-red-600" } as const;

type ConnectionTestSectionProps = { title: string; model: ModelDetail };

/**
 * 마지막 테스트 카드. 숫자 네 칸은 상세 API에 없어 이번에 실행한 결과만 보여 주고 패널을 닫으면 사라짐.
 * 실패한 실행은 오류 내용을 읽어야 하므로 창을 열어 둠
 */
export function ConnectionTestSection({
  title,
  model,
}: ConnectionTestSectionProps) {
  const [testing, setTesting] = useState(false);
  const [lastRun, setLastRun] = useState<ConnectionTestResult>();
  const result =
    model.last_test_status === null
      ? null
      : testResultView(model.last_test_status);
  return (
    <section className="flex flex-col gap-3">
      <div className="flex items-center justify-between gap-3">
        <h3 className="font-bold">{title}</h3>
        <Button variant="secondary" size="sm" onClick={() => setTesting(true)}>
          테스트 실행
        </Button>
      </div>
      <div className="flex flex-col gap-3 rounded-2xl bg-grey-50 p-4">
        <div className="flex items-start justify-between gap-3">
          <div className="flex flex-col gap-0.5">
            <span className="text-caption text-grey-600">마지막 테스트</span>
            <span className="font-bold tabular-nums">
              {model.last_test_at === null
                ? NO_TEST_LABEL
                : timeOrNone(model.last_test_at)}
            </span>
          </div>
          {result && (
            <span
              className={`inline-flex items-center gap-1 text-label font-semibold ${RESULT_CLASS[result.dot]}`}
            >
              <span aria-hidden="true">
                {result.dot === "green" ? "✓" : "✕"}
              </span>
              {result.label}
            </span>
          )}
        </div>
        <TestStatCells result={lastRun} />
        <p className="text-caption text-grey-600 tabular-nums">
          {lastRun === undefined && `${NOT_RUN_HINT} `}
          마지막 성공 {timeOrNone(model.last_success_test_at)}
        </p>
      </div>
      {testing && (
        <ConnectionTestDialog
          model={model}
          onClose={() => setTesting(false)}
          onResult={(run) => {
            setLastRun(run);
            if (run.status === "SUCCESS") setTesting(false);
          }}
        />
      )}
    </section>
  );
}
