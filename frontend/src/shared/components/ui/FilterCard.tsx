import type { FormEventHandler, ReactNode } from "react";
import { Button } from "./Button";

type FilterCardProps = {
  /** 조회 버튼을 눌렀을 때. 검증은 쓰는 쪽의 폼이 한다. */
  onSubmit: FormEventHandler<HTMLFormElement>;
  /** 조건 줄 아래에 보여 줄 오류. id는 잘못된 칸의 aria-describedby와 이어 준다. */
  error?: { id: string; message: string };
  /** 조회 조건 칸들. 한 줄에 놓고, 조회 버튼은 오른쪽 끝에 둔다. */
  children: ReactNode;
};

/**
 * 화면 위쪽의 조회 조건 카드. 조회 버튼을 눌러야 적용하는 화면에서 쓴다.
 * 오류 문구를 칸 아래가 아니라 줄 아래에 두어, 문구 때문에 칸끼리 줄이 어긋나지 않게 한다.
 */
export function FilterCard({ onSubmit, error, children }: FilterCardProps) {
  return (
    <form
      aria-label="조회 조건"
      noValidate
      onSubmit={onSubmit}
      className="rounded-2xl bg-white p-4"
    >
      <div className="flex flex-wrap items-center gap-x-4 gap-y-3">
        {children}
        <Button type="submit" className="ml-auto">
          조회
        </Button>
      </div>
      {error && (
        <p
          id={error.id}
          role="alert"
          className="mt-2 text-label font-medium text-red-600"
        >
          {error.message}
        </p>
      )}
    </form>
  );
}
