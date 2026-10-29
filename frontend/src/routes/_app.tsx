import { createFileRoute, Outlet } from "@tanstack/react-router";
import { Sidebar } from "../shared/components/ui/Sidebar";

// 로그인 화면을 뺀 모든 화면이 쓰는 틀. 주소에는 나타나지 않는다.
export const Route = createFileRoute("/_app")({
  component: AppLayout,
});

function AppLayout() {
  return (
    <div className="flex min-h-screen">
      <Sidebar />
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
  );
}
