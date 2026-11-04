import {
  createFileRoute,
  Outlet,
  redirect,
  useRouterState,
} from "@tanstack/react-router";
import { AssistantWidget } from "../features/assistant/components/AssistantWidget";
import { assistantPageContext } from "../features/assistant/lib/page-context";
import { currentUserQueryOptions } from "../features/auth/api/auth";
import { LogoutButton } from "../features/auth/components/LogoutButton";
import { useLogout } from "../features/auth/hooks/useLogout";
import { useSessionWatch } from "../features/auth/hooks/useSessionWatch";
import { Sidebar } from "../shared/components/ui/Sidebar";
import { AssistantProvider } from "../shared/lib/assistant";

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
  const { queryClient } = Route.useRouteContext();
  const { logout, isPending, isIdle, errorMessage } = useLogout();
  const user = useSessionWatch({ paused: !isIdle });
  const expireSession = async () => {
    if (
      !user ||
      queryClient.getQueryData(currentUserQueryOptions.queryKey)?.user_id !==
        user.user_id
    )
      return;
    await queryClient.cancelQueries({
      queryKey: currentUserQueryOptions.queryKey,
    });
    if (
      queryClient.getQueryData(currentUserQueryOptions.queryKey)?.user_id ===
      user.user_id
    )
      queryClient.setQueryData(currentUserQueryOptions.queryKey, null);
  };
  const page = useRouterState({
    select: (state) => ({
      path: state.location.pathname,
      search: state.matches.at(-1)?.search,
    }),
  });
  const pageContext = assistantPageContext(page.path, page.search);
  return (
    <AssistantProvider>
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
        {user && (
          <AssistantWidget
            key={user.user_id}
            userId={user.user_id}
            onSessionExpired={expireSession}
            pageContext={pageContext}
            onLogout={() => logout()}
            logoutPending={isPending}
            logoutError={errorMessage}
          />
        )}
      </div>
    </AssistantProvider>
  );
}
