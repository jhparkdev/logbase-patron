import { type ReactNode, useId } from "react";
import { formatCount } from "../../lib/format";
import { Badge } from "./Badge";
import { HelpTip } from "./HelpTip";

type SectionCardProps = {
  title: string;
  /** 제목 옆 개수. 예: 등록된 AI 모델 10 */
  count?: number;
  help?: string;
  /** 제목 옆 짧은 안내. 예: 프로젝트명을 누르면 상세 내역을 볼 수 있어요. */
  description?: string;
  /** 오른쪽 끝의 전체보기 같은 이동 */
  action?: ReactNode;
  children: ReactNode;
};

/**
 * 화면의 데이터 블록 하나를 감싸는 흰 카드.
 * 내용 여백은 쓰는 쪽이 정한다. 표는 카드 가장자리까지 붙기 때문이다.
 */
export function SectionCard({
  title,
  count,
  help,
  description,
  action,
  children,
}: SectionCardProps) {
  const titleId = useId();
  return (
    <section
      aria-labelledby={titleId}
      className="relative rounded-2xl bg-white"
    >
      <header className="flex flex-wrap items-center gap-2 px-6 py-5">
        <h2 id={titleId} className="text-section font-bold">
          {title}
        </h2>
        {count !== undefined && <Badge tone="grey">{formatCount(count)}</Badge>}
        {help && <HelpTip text={help} />}
        {description && (
          <p className="text-body-sm text-grey-600">{description}</p>
        )}
        {action && <div className="ml-auto">{action}</div>}
      </header>
      {children}
    </section>
  );
}
