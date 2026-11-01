import { useState } from "react";
import { SidePanel } from "../../../shared/components/ui/SidePanel";
import type { OpenRouterModel } from "../api/models";
import { OpenRouterSearch } from "./OpenRouterSearch";
import { RegisterForm } from "./RegisterForm";

/** 신규 모델 등록 패널. OpenRouter 모델을 고르면 등록 정보 입력이 나타남 */
export function ModelRegisterPanel({ onClose }: { onClose: () => void }) {
  const [selected, setSelected] = useState<OpenRouterModel>();
  return (
    <SidePanel title="신규 모델 등록" onClose={onClose}>
      <div className="flex flex-col gap-6">
        <OpenRouterSearch
          selectedId={selected?.openrouter_model_id}
          onSelect={setSelected}
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
