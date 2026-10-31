import { TextLink } from "../../../shared/components/ui/TextLink";
import type { UsageListView } from "../lib/search";

type ViewAllLinkProps = {
  view: UsageListView;
  /** 표 제목. 같은 화면에 전체보기가 둘이라 화면 낭독기가 구분하게 이름에 붙인다. */
  title: string;
};

/** 요약 화면의 표에서 그 목록의 전체보기로 간다. 조회 조건은 그대로 둔다. */
export function ViewAllLink({ view, title }: ViewAllLinkProps) {
  return (
    <TextLink
      from="/customer-usage"
      to="/customer-usage"
      search={(prev) => ({ ...prev, view })}
      aria-label={`${title} 전체보기`}
      className="text-body-sm"
    >
      전체보기 ›
    </TextLink>
  );
}
