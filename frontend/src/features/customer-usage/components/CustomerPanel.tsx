import { BudgetForm } from "../../../shared/components/budget/BudgetForm";
import { SidePanel } from "../../../shared/components/ui/SidePanel";
import { Skeleton } from "../../../shared/components/ui/Skeleton";

const SUMMARY_LABELS = [
  "확정 비용 (USD)",
  "추정 비용 (USD)",
  "예산 사용률",
] as const;

type CustomerPanelProps = {
  /** 예산을 비교하는 달 "YYYY-MM" */
  budgetMonth: string;
  onClose: () => void;
};

/**
 * 고객 상세 패널. 제목(고객명)과 사용 요약 값은 고객 API를 연결할 때 채우고,
 * 예산 저장은 저장 API를 연결할 때 켠다.
 */
export function CustomerPanel({ budgetMonth, onClose }: CustomerPanelProps) {
  return (
    <SidePanel title="고객 상세" onClose={onClose}>
      <div className="flex flex-col gap-8">
        <section className="flex flex-col gap-3">
          <h3 className="font-bold">{budgetMonth} 사용 요약</h3>
          <div className="grid grid-cols-3 gap-2">
            {SUMMARY_LABELS.map((label) => (
              <div
                key={label}
                className="flex flex-col gap-1 rounded-xl bg-grey-50 p-3"
              >
                <span className="text-caption text-grey-600">{label}</span>
                <Skeleton className="h-6 w-2/3" />
              </div>
            ))}
          </div>
        </section>
        <section className="flex flex-col gap-3">
          <h3 className="font-bold">월 예산</h3>
          <BudgetForm defaultMonth={budgetMonth} onClose={onClose} />
        </section>
      </div>
    </SidePanel>
  );
}
