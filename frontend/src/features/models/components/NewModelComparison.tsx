import { Badge } from "../../../shared/components/ui/Badge";
import { useModelDiscoveries } from "../hooks/useModelDiscoveries";

/** 새로 올라온 모델을 기본 모델과 견준 결과. 비교한 모델이 없으면 그리지 않음 */
export function NewModelComparison() {
  const views = useModelDiscoveries();
  if (views.length === 0) return null;
  return (
    <section
      aria-labelledby="new-model-comparison"
      className="flex flex-col gap-3 rounded-2xl border border-grey-200 bg-white p-5"
    >
      <div>
        <h2 id="new-model-comparison" className="font-bold">
          새 모델 비교 결과
        </h2>
        <p className="text-label text-grey-600">
          기본 모델(최근 가장 많이 쓴 모델)과 같은 시나리오로 호출해 견줬어요.
          답변 길이에 따라 실제 비용은 달라질 수 있어요.
        </p>
      </div>
      <ul className="flex flex-col gap-2">
        {views.map((view) => (
          <li
            key={view.key}
            className="flex flex-col gap-1 rounded-xl border border-grey-100 px-4 py-3"
          >
            <div className="flex items-center gap-3">
              <span className="font-semibold">{view.name}</span>
              <Badge tone={view.tone}>{view.label}</Badge>
            </div>
            {view.lines.map((line) => (
              <p key={line} className="text-body-sm text-grey-700">
                {line}
              </p>
            ))}
          </li>
        ))}
      </ul>
    </section>
  );
}
