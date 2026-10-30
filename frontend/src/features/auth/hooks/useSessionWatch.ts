import { useQuery } from "@tanstack/react-query";
import { useRouter } from "@tanstack/react-router";
import { useEffect } from "react";
import { currentUserQueryOptions } from "../api/auth";

/**
 * 로그인 사용자 조회를 지켜보다가 세션이 끝난 것(null)이 확인되면 로그인 화면으로 보낸다.
 * 만료, 다른 탭에서의 로그아웃이 여기에 해당한다. 로그아웃 중(paused)에는 만료로 오해하지 않게 멈춘다.
 */
export function useSessionWatch({ paused }: { paused: boolean }) {
  const { data: user } = useQuery(currentUserQueryOptions);
  const router = useRouter();
  const sessionEnded = user === null && !paused;

  useEffect(() => {
    if (!sessionEnded) {
      return;
    }
    router.navigate({
      to: "/login",
      search: { redirect: router.state.location.href, reason: "expired" },
    });
  }, [sessionEnded, router]);

  return user;
}
