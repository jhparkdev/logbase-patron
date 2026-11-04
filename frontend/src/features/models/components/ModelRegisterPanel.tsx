import { useState } from "react";
import { SidePanel } from "../../../shared/components/ui/SidePanel";
import { NEW_MODELS_DAYS, type OpenRouterModel } from "../api/models";
import { OpenRouterSearch } from "./OpenRouterSearch";
import { RegisterForm } from "./RegisterForm";

type ModelRegisterPanelProps = {
  onClose: () => void;
  /** true면 최근 올라온 새 모델만 보여 주며 시작함(신규 모델 알림에서 열 때) */
  onlyNew?: boolean;
};

/** 신규 모델 등록 패널. OpenRouter 모델을 고르면 등록 정보 입력이 나타남 */
export function ModelRegisterPanel({
  onClose,
  onlyNew = false,
}: ModelRegisterPanelProps) {
  const [selected, setSelected] = useState<OpenRouterModel>();
  const [newOnly, setNewOnly] = useState(onlyNew);
  return (
    <SidePanel title="신규 모델 등록" onClose={onClose}>
      <div className="flex flex-col gap-6">
        <OpenRouterSearch
          // 보는 범위를 바꾸면 검색어와 페이지를 처음으로 되돌림
          key={newOnly ? "new" : "all"}
          selectedId={selected?.openrouter_model_id}
          onSelect={setSelected}
          newDays={newOnly ? NEW_MODELS_DAYS : undefined}
          onShowAll={() => setNewOnly(false)}
        />
        {selected && (
          // 모델을 바꾸면 표시 이름의 처음 값도 새 모델로 다시 채움
          <RegisterForm
            key={selected.openrouter_model_id}
            model={selected}
            onClose={onClose}
          />
        )}
      </div>
    </SidePanel>
  );
}
