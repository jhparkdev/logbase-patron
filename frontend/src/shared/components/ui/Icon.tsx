type IconProps = {
  /** import한 SVG 경로. 모양만 쓰고, 색은 감싼 글자색을 따른다. */
  src: string;
  /** 크기(예: size-4)와 색(예: text-grey-600) */
  className: string;
};

export function Icon({ src, className }: IconProps) {
  return (
    <span
      aria-hidden="true"
      className={`inline-block shrink-0 bg-current mask-contain mask-center mask-no-repeat ${className}`}
      // 빌드에서 작은 SVG는 작은따옴표가 든 data URI가 되므로 큰따옴표로 감싼다.
      style={{ maskImage: `url("${src}")` }}
    />
  );
}
