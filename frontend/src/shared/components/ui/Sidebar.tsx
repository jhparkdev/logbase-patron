import { Link } from "@tanstack/react-router";
import logoMark from "../../../assets/logo.svg";

const NAV_ITEMS = [
  { to: "/customer-usage", label: "고객 AI 사용 현황" },
  { to: "/internal-budget", label: "내부 AI 예산 관리" },
  { to: "/models", label: "AI 모델 관리" },
  { to: "/simulator", label: "AI 모델 시뮬레이터" },
  { to: "/simulation-history", label: "시뮬레이션 결과 이력" },
] as const;

export function Sidebar() {
  return (
    <aside className="flex w-60 shrink-0 flex-col gap-6 bg-grey-900 px-3 py-4">
      <div className="flex items-center gap-2 px-2">
        <span className="grid size-7 place-items-center rounded-lg bg-brand">
          <img src={logoMark} alt="" />
        </span>
        <span className="font-bold text-white">
          LOGBASE <span className="font-medium text-grey-400">Patron</span>
        </span>
      </div>
      <nav aria-label="주 메뉴" className="flex flex-col gap-0.5">
        {NAV_ITEMS.map((item) => (
          <Link
            key={item.to}
            to={item.to}
            className="rounded-control px-3 py-2 font-medium"
            activeProps={{ className: "bg-white/12 font-semibold text-white" }}
            inactiveProps={{ className: "text-grey-400 hover:bg-white/8" }}
          >
            {item.label}
          </Link>
        ))}
      </nav>
    </aside>
  );
}
