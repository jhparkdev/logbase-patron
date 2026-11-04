/**
 * 이전 결과를 보여 주는 동안 새 조건으로 다시 불러오고 있음을 알리는 얇은 막대.
 * 감싼 상자에 relative가 있어야 위쪽 가장자리에 붙는다.
 */
export function RefreshingBar() {
  return (
    <div
      role="progressbar"
      aria-label="새 조건으로 불러오는 중"
      className="absolute inset-x-0 top-0 h-0.5 bg-brand motion-safe:animate-pulse"
    />
  );
}
