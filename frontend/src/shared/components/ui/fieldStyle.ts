/**
 * 입력 칸 공통 모양: 모서리, 테두리, 배경, 글자, 포커스, 잘못된 입력 표시.
 * 높이와 안쪽 여백, 너비는 쓰는 쪽이 정한다. 여러 줄 입력 칸처럼 높이를 따로 정할 때 쓴다.
 */
export const FIELD_BOX_CLASS =
  "rounded-control border border-neutral-weak bg-grey-50 text-body-sm focus-visible:border-brand focus-visible:outline-none aria-invalid:border-red-500";

/** 한 줄 입력 칸(입력, 선택 상자, 날짜). 높이는 TDS Medium 38px이다. */
export const FIELD_CLASS = `h-9.5 ${FIELD_BOX_CLASS}`;
