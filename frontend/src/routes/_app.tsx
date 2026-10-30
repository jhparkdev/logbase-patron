import { createFileRoute, Outlet, redirect } from "@tanstack/react-router";
import { currentUserQueryOptions } from "../features/auth/api/auth";
import { LogoutButton } from "../features/auth/components/LogoutButton";
import { useLogout } from "../features/auth/hooks/useLogout";
import { useSessionWatch } from "../features/auth/hooks/useSessionWatch";
import { Sidebar } from "../shared/components/ui/Sidebar";

// 로그인 화면을 뺀 모든 화면이 쓰는 틀. 주소에는 나타나지 않는다.
export const Route = createFileRoute("/_app")({
  // 로그인하지 않은 상태로 들어오면 로그인 화면으로 보내고, 로그인 뒤 돌아올 주소를 남긴다.
  beforeLoad: async ({ context, location }) => {
    const user = await context.queryClient.ensureQueryData(
      currentUserQueryOptions,
    );
    if (!user) {
      throw redirect({ to: "/login", search: { redirect: location.href } });
    }
  },
  component: AppLayout,
});

function AppLayout() {
  const { logout, isPending, isIdle, errorMessage } = useLogout();
  useSessionWatch({ paused: !isIdle });
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
          <LogoutButton
            onLogout={() => logout()}
            isPending={isPending}
            errorMessage={errorMessage}
          />
        </header>
        <main className="flex flex-col gap-6 p-8">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
