import type { components } from "../../api/schema";
import { budgetStatusBadge } from "../../lib/budget";
import { Badge } from "../ui/Badge";
import { Button } from "../ui/Button";

export function BudgetStatusNotice({
  status,
  onClear,
}: {
  status: components["schemas"]["BudgetStatus"];
  onClear: () => void;
}) {
  const badge = budgetStatusBadge(status);
  return (
    <div className="flex items-center gap-2 text-body-sm text-grey-700">
      <span>예산 목록 조건</span>
      <Badge tone={badge.tone}>{badge.label}</Badge>
      <Button variant="secondary" size="sm" onClick={onClear}>
        예산 상태 조건 해제
      </Button>
    </div>
  );
}
