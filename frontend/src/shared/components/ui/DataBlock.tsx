import { QueryErrorResetBoundary } from "@tanstack/react-query";
import { Component, type ReactNode, Suspense } from "react";
import { Button } from "./Button";
import { Result } from "./Result";

type DataBlockProps = {
  /** 처음 불러오는 동안 보여 줄 모양 */
  fallback: ReactNode;
  /** 불러오지 못했을 때의 제목 */
  errorTitle: string;
  /** 조회 조건. 바뀌면 실패 상태를 지우고 새 조건으로 다시 불러온다. */
  resetKey: string;
  children: ReactNode;
};

/** 데이터 블록 하나의 로딩과 실패를 맡는다. 한 블록이 실패해도 다른 블록은 그대로다. */
export function DataBlock({
  fallback,
  errorTitle,
  resetKey,
  children,
}: DataBlockProps) {
  return (
    <QueryErrorResetBoundary>
      {({ reset }) => (
        <FailureBoundary
          errorTitle={errorTitle}
          resetKey={resetKey}
          onRetry={reset}
        >
          <Suspense fallback={fallback}>{children}</Suspense>
        </FailureBoundary>
      )}
    </QueryErrorResetBoundary>
  );
}

type FailureBoundaryProps = {
  errorTitle: string;
  resetKey: string;
  onRetry: () => void;
  children: ReactNode;
};

// 렌더링 중 던진 오류는 클래스 컴포넌트의 오류 경계만 받을 수 있다.
class FailureBoundary extends Component<
  FailureBoundaryProps,
  { failed: boolean }
> {
  state = { failed: false };

  static getDerivedStateFromError() {
    return { failed: true };
  }

  componentDidUpdate(previous: FailureBoundaryProps) {
    if (this.state.failed && previous.resetKey !== this.props.resetKey) {
      this.props.onRetry();
      this.setState({ failed: false });
    }
  }

  render() {
    if (!this.state.failed) {
      return this.props.children;
    }
    return (
      <Result
        title={this.props.errorTitle}
        description="잠시 후 다시 시도해 주세요."
        action={
          <Button
            variant="secondary"
            size="sm"
            onClick={() => {
              this.props.onRetry();
              this.setState({ failed: false });
            }}
          >
            다시 시도
          </Button>
        }
      />
    );
  }
}
