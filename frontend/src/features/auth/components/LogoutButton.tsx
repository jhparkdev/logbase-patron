import offIcon from "../../../assets/off.svg";
import { Icon } from "../../../shared/components/ui/Icon";

type LogoutButtonProps = {
  onLogout: () => void;
  isPending: boolean;
  errorMessage?: string;
};

/** 화면 틀 헤더 오른쪽 끝의 종료 아이콘(designs/Header.png). 글자가 없어 이름과 설명을 속성으로 준다. */
export function LogoutButton({
  onLogout,
  isPending,
  errorMessage,
}: LogoutButtonProps) {
  return (
    <div className="ml-auto flex items-center gap-3">
      {errorMessage && (
        <p role="alert" className="text-label text-red-600">
          {errorMessage}
        </p>
      )}
      <button
        type="button"
        aria-label="로그아웃"
        title="로그아웃"
        onClick={onLogout}
        disabled={isPending}
        className="grid size-9 place-items-center rounded-lg text-grey-700 transition-colors hover:bg-grey-100 hover:text-grey-900 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand disabled:cursor-not-allowed disabled:opacity-40"
      >
        <Icon src={offIcon} className="size-4.5" />
      </button>
    </div>
  );
}
