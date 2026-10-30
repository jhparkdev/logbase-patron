import { SidePanel } from "../../../shared/components/ui/SidePanel";
import { Skeleton } from "../../../shared/components/ui/Skeleton";

// 섹션별 데이터 자리의 높이는 시안의 입력 칸·카드 배치에 맞춘다.
const SECTIONS = [
  { title: "기본 정보", placeholder: "h-40" },
  { title: "토큰 단가 (USD/1K)", placeholder: "h-20" },
  { title: "연결 테스트", placeholder: "h-36" },
  { title: "운영 상태 관리", placeholder: "h-24" },
] as const;

/** 모델 상세 패널. 내용은 모델 상세 API가 생기면 채우고, 그 전까지는 데이터 자리만 보여 준다. */
export function ModelDetailPanel({ onClose }: { onClose: () => void }) {
  return (
    <SidePanel title="모델 상세" onClose={onClose}>
      <div className="flex flex-col gap-8">
        {SECTIONS.map((section) => (
          <section key={section.title} className="flex flex-col gap-3">
            <h3 className="font-bold">{section.title}</h3>
            <Skeleton className={section.placeholder} />
          </section>
        ))}
      </div>
    </SidePanel>
  );
}
