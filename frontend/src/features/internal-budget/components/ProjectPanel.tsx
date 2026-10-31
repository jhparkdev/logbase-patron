import { SidePanel } from "../../../shared/components/ui/SidePanel";
import { Skeleton } from "../../../shared/components/ui/Skeleton";
import { BudgetForm } from "./BudgetForm";

type ProjectPanelProps = {
  /** 예산을 비교하는 달 "YYYY-MM" */
  month: string;
  onClose: () => void;
};

/**
 * 프로젝트 상세 패널. 제목(프로젝트명)과 사용 요약은 프로젝트 API가 생기면 채우고,
 * 그 전까지 요약은 불러오는 중 모양이다. 예산 저장은 저장 API가 생기면 연결한다.
 */
export function ProjectPanel({ month, onClose }: ProjectPanelProps) {
  return (
    <SidePanel title="프로젝트 상세" onClose={onClose}>
      <div className="flex flex-col gap-8">
        <section className="flex flex-col gap-3">
          <h3 className="font-bold">{month} 사용 요약</h3>
          <div className="grid grid-cols-3 gap-2">
            <Skeleton className="h-16" />
            <Skeleton className="h-16" />
            <Skeleton className="h-16" />
          </div>
        </section>
        <section className="flex flex-col gap-3">
          <h3 className="font-bold">월 예산</h3>
          <BudgetForm defaultMonth={month} onClose={onClose} />
        </section>
      </div>
    </SidePanel>
  );
}
