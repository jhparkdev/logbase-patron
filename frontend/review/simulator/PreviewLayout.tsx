import { Outlet } from "@tanstack/react-router";
import { Sidebar } from "../../src/shared/components/ui/Sidebar";

export function PreviewLayout() {
  return (
    <>
      <div className="flex items-center justify-between gap-4 bg-blue-50 px-8 py-3 text-body-sm text-blue-700">
        <p>
          <strong>P-04 데이터 표시 예시</strong> · 기존 mock 한 건의 입력과
          결과입니다. 편집해도 저장된 결과는 바뀌지 않습니다. 실제 AI 호출은
          하지 않습니다. 모델별 튜닝의 지원 항목·범위·선택지는 검토용
          예시입니다.
        </p>
        <a
          href="/simulator"
          className="shrink-0 rounded-lg font-semibold underline underline-offset-4 focus-visible:outline-2 focus-visible:outline-brand"
        >
          실제 P-04로 이동
        </a>
      </div>
      <div className="flex min-h-screen">
        <Sidebar activeTo="/simulator" />
        <div className="flex min-w-0 flex-1 flex-col">
          <header className="flex h-16 items-center gap-1 border-b border-grey-200 bg-white px-8 text-body-sm">
            <span className="font-semibold">LOGBASE Patron</span>
            <span aria-hidden="true" className="text-grey-400">
              ›
            </span>
            <span className="text-grey-600">운영 콘솔</span>
          </header>
          <main className="flex flex-col gap-6 p-8">
            <Outlet />
          </main>
        </div>
      </div>
    </>
  );
}
