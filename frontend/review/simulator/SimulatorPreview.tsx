import { SimulatorPage } from "../../src/features/simulator/components/SimulatorPage";
import { previewData } from "./preview-data.fixture";

export function SimulatorPreview() {
  return (
    <SimulatorPage
      initialValues={previewData.initialValues}
      choices={previewData.choices}
      scenarios={previewData.scenarios}
      view={{ kind: "ready", run: previewData.run }}
    />
  );
}
