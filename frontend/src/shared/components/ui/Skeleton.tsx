/** 데이터를 기다리는 자리. 실제 컴포넌트와 같은 크기를 className으로 준다. */
export function Skeleton({ className }: { className: string }) {
  return (
    <div
      aria-hidden="true"
      className={`rounded-lg bg-grey-100 motion-safe:animate-pulse ${className}`}
    />
  );
}
