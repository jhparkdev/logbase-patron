import dropDownIcon from "../../../assets/dropDown.svg";
import { pageCount, visiblePages } from "../../lib/pagination";
import { Icon } from "./Icon";

type PaginationProps = {
  total: number;
  pageSize: number;
  page: number;
  onPageChange: (page: number) => void;
};

/** 표 아래의 페이지 이동. 전체 건수는 카드 제목(SectionCard의 count)에 보여 준다. */
export function Pagination({
  total,
  pageSize,
  page,
  onPageChange,
}: PaginationProps) {
  const lastPage = pageCount(total, pageSize);
  return (
    <nav
      aria-label="페이지"
      className="flex justify-end px-6 py-4 text-body-sm text-grey-600"
    >
      <div className="flex items-center gap-1">
        <PageArrow
          label="이전 페이지"
          disabled={page <= 1}
          onClick={() => onPageChange(page - 1)}
          direction="prev"
        />
        {visiblePages(page, lastPage).map((number) => (
          <button
            key={number}
            type="button"
            aria-current={number === page ? "page" : undefined}
            onClick={() => onPageChange(number)}
            className="grid size-8 place-items-center rounded-lg font-semibold tabular-nums hover:bg-grey-100 focus-visible:outline-2 focus-visible:outline-brand aria-[current=page]:bg-brand aria-[current=page]:text-white"
          >
            {number}
          </button>
        ))}
        <PageArrow
          label="다음 페이지"
          disabled={page >= lastPage}
          onClick={() => onPageChange(page + 1)}
          direction="next"
        />
      </div>
    </nav>
  );
}

// 아래 화살표 아이콘(dropDown)을 돌려 이전·다음 화살표로 쓴다.
const ARROW_ROTATE = { prev: "rotate-90", next: "-rotate-90" } as const;

function PageArrow({
  label,
  disabled,
  onClick,
  direction,
}: {
  label: string;
  disabled: boolean;
  onClick: () => void;
  direction: keyof typeof ARROW_ROTATE;
}) {
  return (
    <button
      type="button"
      aria-label={label}
      disabled={disabled}
      onClick={onClick}
      className="grid size-8 place-items-center rounded-lg hover:bg-grey-100 focus-visible:outline-2 focus-visible:outline-brand disabled:cursor-not-allowed disabled:opacity-40"
    >
      <Icon
        src={dropDownIcon}
        className={`h-1.5 w-2.5 ${ARROW_ROTATE[direction]}`}
      />
    </button>
  );
}
