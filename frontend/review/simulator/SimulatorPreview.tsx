import { SimulatorPage } from "../../src/features/simulator/components/SimulatorPage";
import { previewData } from "./preview-data.fixture";

export function SimulatorPreview() {
  // 검토 페이지에서만 유지한다. 실제 계정의 즐겨찾기를 조회하거나 저장하지 않는다.
  const [favoriteKeys, setFavoriteKeys] = useState<string[]>([]);
  return (
    <SimulatorPage
      initialValues={previewData.initialValues}
      choices={previewData.choices}
      scenarios={previewData.scenarios}
      view={{ kind: "ready", run: previewData.run }}
      favorites={{
        kind: "ready",
        keys: favoriteKeys,
        onSet: (key, favorite) =>
          setFavoriteKeys((keys) =>
            favorite
              ? [...new Set([...keys, key])]
              : keys.filter((value) => value !== key),
          ),
      }}
    />
  );
}

import { useState } from "react";
