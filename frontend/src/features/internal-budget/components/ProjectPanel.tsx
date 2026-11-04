import { useQuery } from "@tanstack/react-query";
import { ApiError } from "../../../shared/api/client";
import { Button } from "../../../shared/components/ui/Button";
import { Result } from "../../../shared/components/ui/Result";
import { SidePanel } from "../../../shared/components/ui/SidePanel";
import { Skeleton } from "../../../shared/components/ui/Skeleton";
import { projectDetailQuery } from "../api/budget";
import { ProjectPanelContent } from "./ProjectPanelContent";

type ProjectPanelProps = {
  projectId: number;
  /** 예산을 비교하는 달 "YYYY-MM" */
  month: string;
  onClose: () => void;
};

/** 프로젝트 상세 패널. 제목은 프로젝트명이고, 불러오는 동안에는 "프로젝트 상세"로 둔다. */
export function ProjectPanel({ projectId, month, onClose }: ProjectPanelProps) {
  const detail = useQuery(projectDetailQuery(projectId, month));
  return (
    <SidePanel
      title={detail.data?.project_name ?? "프로젝트 상세"}
      onClose={onClose}
    >
      {detail.isPending && (
        // 요약 카드와 칸 3개와 같은 배치로 둔다.
        <div className="flex flex-col gap-6">
          <Skeleton className="h-64 rounded-2xl" />
          <div className="grid grid-cols-3 gap-2">
            <Skeleton className="h-16" />
            <Skeleton className="h-16" />
            <Skeleton className="h-16" />
          </div>
        </div>
      )}
      {detail.isError && (
        <DetailError error={detail.error} onRetry={() => detail.refetch()} />
      )}
      {detail.data && (
        <ProjectPanelContent
          projectId={projectId}
          month={month}
          detail={detail.data}
          onClose={onClose}
        />
      )}
    </SidePanel>
  );
}

/** 없는 번호는 다시 해도 결과가 같아 다시 시도를 두지 않는다. */
function DetailError({
  error,
  onRetry,
}: {
  error: Error;
  onRetry: () => void;
}) {
  if (error instanceof ApiError && error.code === "NOT_FOUND") {
    return (
      <Result
        title="프로젝트를 찾을 수 없어요"
        description="목록에서 프로젝트를 다시 골라 주세요."
      />
    );
  }
  return (
    <Result
      title="프로젝트 상세를 불러오지 못했어요"
      description="잠시 후 다시 시도해 주세요."
      action={
        <Button variant="secondary" size="sm" onClick={onRetry}>
          다시 시도
        </Button>
      }
    />
  );
}
