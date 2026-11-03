import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { ApiError } from "../../../shared/api/client";
import { Button } from "../../../shared/components/ui/Button";
import { loginAssistant, sessionOptions } from "../api/assistant";

const schema = z.object({
  email: z.string().min(1, "이메일을 입력해 주세요.").max(254),
  password: z.string().min(1, "비밀번호를 입력해 주세요.").max(128),
});

export function AssistantLogin() {
  const queryClient = useQueryClient();
  const form = useForm<z.infer<typeof schema>>({
    resolver: zodResolver(schema),
    defaultValues: { email: "", password: "" },
  });
  const login = useMutation({
    mutationFn: () => loginAssistant(form.getValues()),
    retry: false,
    gcTime: 0,
    onSuccess: async (user) => {
      // 로그인 전에 시작한 세션 확인이 뒤늦게 성공 결과를 덮어쓰지 않게 한다.
      await queryClient.cancelQueries({ queryKey: sessionOptions.queryKey });
      form.reset();
      queryClient.setQueryData(sessionOptions.queryKey, user);
    },
  });
  return (
    <form
      noValidate
      onSubmit={form.handleSubmit(() => login.mutate())}
      className="space-y-4 p-5"
    >
      <p className="text-body-sm text-grey-700">
        사용량·비용·모델 정보와 실행 이력을 조회하려면 로그인해 주세요.
      </p>
      <label className="block text-label font-semibold">
        이메일
        <input
          type="email"
          autoComplete="username"
          {...form.register("email")}
          className="mt-2 w-full rounded-control border border-grey-200 bg-grey-50 px-3 py-2 text-body-sm focus:outline-brand"
        />
      </label>
      {form.formState.errors.email && (
        <p role="alert" className="text-caption text-red-600">
          이메일을 입력해 주세요.
        </p>
      )}
      <label className="block text-label font-semibold">
        비밀번호
        <input
          type="password"
          autoComplete="current-password"
          {...form.register("password")}
          className="mt-2 w-full rounded-control border border-grey-200 bg-grey-50 px-3 py-2 text-body-sm focus:outline-brand"
        />
      </label>
      {form.formState.errors.password && (
        <p role="alert" className="text-caption text-red-600">
          비밀번호를 입력해 주세요.
        </p>
      )}
      {login.isError && (
        <p role="alert" className="text-body-sm text-red-600">
          {login.error instanceof ApiError
            ? login.error.message
            : "로그인하지 못했어요. 다시 시도해 주세요."}
        </p>
      )}
      <Button type="submit" disabled={login.isPending} className="w-full">
        {login.isPending ? "로그인 중" : "로그인"}
      </Button>
    </form>
  );
}
