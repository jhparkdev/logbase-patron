import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "@tanstack/react-router";
import { currentUserQueryOptions, logout } from "../api/auth";

export const LOGOUT_FAILED_MESSAGE =
  "로그아웃하지 못했어요. 다시 시도해 주세요.";

/** 서버 로그아웃이 성공하면 이전 사용자의 요청을 취소하고 캐시를 비운 뒤 로그인 화면으로 간다. */
export function useLogout() {
  const queryClient = useQueryClient();
  const router = useRouter();
  const mutation = useMutation({
    mutationFn: logout,
    onSuccess: async () => {
      await queryClient.cancelQueries();
      // 로그인 화면의 beforeLoad가 "이미 로그인함"으로 보지 않게 사용자 캐시를 먼저 비운다.
      queryClient.setQueryData(currentUserQueryOptions.queryKey, null);
      await router.navigate({ to: "/login" });
      // 다른 사람의 데이터가 다시 보이지 않게 화면을 떠난 뒤 캐시 전체를 지운다.
      queryClient.clear();
    },
  });
  return {
    logout: mutation.mutate,
    isPending: mutation.isPending,
    /** 로그아웃을 시작하지 않은 상태. 세션 감시가 로그아웃을 만료로 오해하지 않도록 쓴다. */
    isIdle: mutation.isIdle,
    errorMessage: mutation.error ? LOGOUT_FAILED_MESSAGE : undefined,
  };
}
