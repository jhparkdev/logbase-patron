import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "@tanstack/react-router";
import { currentUserQueryOptions, login } from "../api/auth";
import { loginErrorMessage } from "../lib/loginErrorMessage";

/** 로그인 요청을 보내고, 성공하면 사용자 캐시를 채운 뒤 주어진 주소로 이동한다. */
export function useLogin(afterLoginHref: string) {
  const queryClient = useQueryClient();
  const router = useRouter();
  const mutation = useMutation({
    mutationFn: login,
    onSuccess: async (user) => {
      // 보호된 화면의 beforeLoad가 서버에 다시 묻지 않도록 응답으로 캐시를 채운다.
      queryClient.setQueryData(currentUserQueryOptions.queryKey, user);
      await router.navigate({ href: afterLoginHref });
    },
  });
  return {
    submit: mutation.mutate,
    isPending: mutation.isPending,
    errorMessage: mutation.error
      ? loginErrorMessage(mutation.error)
      : undefined,
  };
}
