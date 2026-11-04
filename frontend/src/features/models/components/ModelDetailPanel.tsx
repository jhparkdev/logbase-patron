import { useQuery } from "@tanstack/react-query";
import { ApiError } from "../../../shared/api/client";
import { Button } from "../../../shared/components/ui/Button";
import { Result } from "../../../shared/components/ui/Result";
import { SidePanel } from "../../../shared/components/ui/SidePanel";
import { Skeleton } from "../../../shared/components/ui/Skeleton";
import { modelDetailQuery } from "../api/models";
import { ModelDetailContent, SECTION_TITLES } from "./ModelDetailContent";

// 섹션별 로딩 자리의 높이는 실제 내용에 맞춤
const SKELETON_SECTIONS = [
  { title: SECTION_TITLES.basic, height: "h-80" },
  { title: SECTION_TITLES.price, height: "h-24" },
  { title: SECTION_TITLES.ranking, height: "h-32" },
  { title: SECTION_TITLES.test, height: "h-48" },
  { title: SECTION_TITLES.status, height: "h-40" },
] as const;

type ModelDetailPanelProps = { modelId: number; onClose: () => void };

/** 모델 상세 패널. 제목은 표시 이름이고, 불러오는 동안에는 "모델 상세"로 둠 */
export function ModelDetailPanel({ modelId, onClose }: ModelDetailPanelProps) {
  const detail = useQuery(modelDetailQuery(modelId));
  return (
    <SidePanel
      title={detail.data?.display_name ?? "모델 상세"}
      onClose={onClose}
    >
      {detail.isPending && <PanelSkeleton />}
      {detail.isError &&
        (detail.error instanceof ApiError &&
        detail.error.code === "NOT_FOUND" ? (
          // 없는 번호는 다시 시도해도 같으므로 버튼을 두지 않음
          <Result
            title="모델을 찾을 수 없어요"
            description="목록에서 모델을 다시 골라 주세요."
          />
        ) : (
          <Result
            title="모델 상세를 불러오지 못했어요"
            description="잠시 후 다시 시도해 주세요."
            action={
              <Button
                variant="secondary"
                size="sm"
                onClick={() => detail.refetch()}
              >
                다시 시도
              </Button>
            }
          />
        ))}
      {detail.data && <ModelDetailContent model={detail.data} />}
    </SidePanel>
  );
}

function PanelSkeleton() {
  return (
    <div className="flex flex-col gap-8">
      {SKELETON_SECTIONS.map((section) => (
        <section key={section.title} className="flex flex-col gap-3">
          <h3 className="font-bold">{section.title}</h3>
          <Skeleton className={section.height} />
        </section>
      ))}
    </div>
  );
}
