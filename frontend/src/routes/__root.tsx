import type { QueryClient } from "@tanstack/react-query";
import { createRootRouteWithContext, Outlet } from "@tanstack/react-router";

// loader가 쿼리 캐시를 쓰도록 router context로 받는다(main.tsx, test/renderAt.tsx가 넘긴다).
export const Route = createRootRouteWithContext<{ queryClient: QueryClient }>()(
  {
    component: Outlet,
  },
);
