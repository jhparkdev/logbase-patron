import { dbMock } from "../../src/features/simulator/components/dbMock.fixture";
import {
  PARAMETER_NAMES,
  type TuningParameter,
} from "../../src/features/simulator/lib/parameters";
import type { ModelChoice } from "../../src/features/simulator/lib/presentation";

// 검토용 가상 지원 정보다. 실제 모델의 지원 여부·범위·선택지를 나타내지 않는다.
const exampleParameters: readonly TuningParameter[] = [
  { key: "temperature", kind: "number", min: 0, max: 2, step: 0.01 },
  { key: "maxTokens", kind: "number", min: 1, max: 4096, step: 1 },
  {
    key: "reasoningEffort",
    kind: "choice",
    options: [
      { value: "low", label: "낮음" },
      { value: "medium", label: "보통" },
      { value: "high", label: "높음" },
    ],
  },
];

export const tuningPreviewChoices: ModelChoice[] = dbMock.choices.map(
  (choice) => {
    // 첫 모델은 선택형 설정, 두 번째는 숫자형만, 나머지는 미제공 상태를 검토한다.
    const tuningParameters =
      choice.key === "1:mock-provider-moonshot"
        ? exampleParameters
        : choice.key === "2:DekaLLM"
          ? exampleParameters.filter((parameter) => parameter.kind === "number")
          : [];
    return {
      ...choice,
      tuningParameters,
      supportedParameters: [
        ...new Set([
          ...choice.supportedParameters,
          ...tuningParameters.map(
            (parameter) => PARAMETER_NAMES[parameter.key],
          ),
        ]),
      ],
    };
  },
);
