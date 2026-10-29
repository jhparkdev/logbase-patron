import { createLink } from "@tanstack/react-router";
import type { ComponentProps } from "react";

function UnderlinedAnchor({ className = "", ...props }: ComponentProps<"a">) {
  return (
    <a
      className={`rounded-sm font-semibold text-blue-600 underline underline-offset-4 hover:text-blue-700 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand ${className}`}
      {...props}
    />
  );
}

/** 표 안의 이름처럼 다른 화면으로 가는 글자 링크. 라우터 Link와 같은 props를 받는다. */
export const TextLink = createLink(UnderlinedAnchor);
