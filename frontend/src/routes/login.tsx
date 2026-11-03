import { createFileRoute, redirect } from "@tanstack/react-router";
import { useId } from "react";
import { z } from "zod";
import logoMark from "../assets/logo.svg";
import { currentUserQueryOptions } from "../features/auth/api/auth";
import { LoginForm } from "../features/auth/components/LoginForm";
import { useLogin } from "../features/auth/hooks/useLogin";
import { safeRedirectTarget } from "../features/auth/lib/redirectTarget";
import { Notice } from "../shared/components/ui/Notice";

// 로그인 뒤 돌아갈 주소. 외부 입력이라 검증하고, 앱 밖으로 보내는 값은 safeRedirectTarget이 기본 화면으로 바꾼다.
const searchSchema = z.object({
  redirect: z.string().optional().catch(undefined),
  // 세션이 끝나 돌아온 경우. 화면 틀의 세션 감시가 붙인다.
  reason: z.enum(["expired"]).optional().catch(undefined),
});

export const Route = createFileRoute("/login")({
  validateSearch: searchSchema,
  beforeLoad: async ({ context, search }) => {
    // 이미 로그인한 상태면 로그인 화면 대신 가려던 화면으로 보낸다.
    const user = await context.queryClient.ensureQueryData(
      currentUserQueryOptions,
    );
    if (user) {
      throw redirect({ href: safeRedirectTarget(search.redirect) });
    }
  },
  component: LoginPage,
});

function LoginPage() {
  const { redirect: target, reason } = Route.useSearch();
  const { submit, isPending, errorMessage } = useLogin(
    safeRedirectTarget(target),
  );
  const titleId = useId();

  return (
    <main className="grid min-h-screen place-items-center p-8">
      <section
        aria-labelledby={titleId}
        className="flex w-100 flex-col gap-8 rounded-2xl bg-white p-8"
      >
        <header className="flex flex-col gap-6">
          <div className="flex items-center gap-2">
            <span className="grid size-7 place-items-center rounded-lg bg-brand">
              <img src={logoMark} alt="" />
            </span>
            <span className="font-bold">
              LOGBASE <span className="font-medium text-grey-600">Patron</span>
            </span>
          </div>
          <div className="flex flex-col gap-1">
            <h1 id={titleId} className="text-title font-bold">
              로그인
            </h1>
            <p className="text-grey-700">관리자 계정으로 로그인해 주세요.</p>
          </div>
        </header>
        {reason === "expired" && (
          <Notice
            title="세션이 만료됐어요"
            description="다시 로그인해 주세요."
          />
        )}
        <LoginForm
          onSubmit={submit}
          isPending={isPending}
          errorMessage={errorMessage}
        />
      </section>
    </main>
  );
}
