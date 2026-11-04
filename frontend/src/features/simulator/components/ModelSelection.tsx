import { type ReactNode, useEffect, useRef, useState } from "react";
import { useFieldArray, useFormContext, useWatch } from "react-hook-form";
import plusIcon from "../../../assets/plus.svg";
import searchIcon from "../../../assets/search.svg";
import { Badge } from "../../../shared/components/ui/Badge";
import { Button } from "../../../shared/components/ui/Button";
import { Icon } from "../../../shared/components/ui/Icon";
import {
  comparisonCounts,
  createComparison,
  reconcileComparisons,
} from "../lib/comparisons";
import type { ModelFavoritesView } from "../lib/favorites";
import type { SimulatorDraft, SimulatorFormValues } from "../lib/form";
import { MODEL_LIMITS } from "../lib/limits";
import { choicesForOutput } from "../lib/output";
import type { ModelChoice, ScenarioChoice } from "../lib/presentation";
import { FieldError } from "./InputFields";
import { ModelComparisonCard } from "./ModelComparisonCard";
import { ModelPickerDialog } from "./ModelPickerDialog";
import { StepHeading } from "./StepHeading";

const EMPTY_SLOT_KEYS = Array.from(
  { length: MODEL_LIMITS.max },
  (_, index) => `empty-slot-${index + 1}`,
);

export function ModelSelection({
  choices,
  scenarios = [],
  unavailable,
  favorites,
  settings,
  notice,
}: {
  choices: ModelChoice[];
  scenarios?: ScenarioChoice[];
  unavailable: boolean;
  favorites?: ModelFavoritesView;
  /** 공통 설정처럼 모델 카드 위에 두는 영역 */
  settings?: ReactNode;
  /** 모델 목록을 못 받았을 때의 안내 */
  notice?: ReactNode;
}) {
  const {
    control,
    getValues,
    setValue,
    trigger: validate,
    formState: { errors },
  } = useFormContext<SimulatorFormValues, unknown, SimulatorDraft>();
  const { fields, replace, append, remove } = useFieldArray({
    control,
    name: "comparisons",
  });
  const [
    comparisons,
    files,
    existingAssetIds,
    jsonSchema,
    mode,
    scenarioKey,
    temperature,
    maxTokens,
    reasoningEffort,
    outputType,
  ] = useWatch({
    control,
    name: [
      "comparisons",
      "files",
      "existingAssetIds",
      "jsonSchema",
      "mode",
      "scenarioKey",
      "temperature",
      "maxTokens",
      "reasoningEffort",
      "outputType",
    ],
  });
  const hasImages = files.length + existingAssetIds.length > 0;
  const imageOutput = outputType === "IMAGE";
  // 이미지 생성 실행에는 Schema를 보내지 않으므로 Schema 지원 여부로 경고하지 않는다
  const hasSchema = !imageOutput && jsonSchema.trim().length > 0;
  const scenario =
    mode === "scenario"
      ? scenarios.find((item) => item.key === scenarioKey)
      : undefined;
  const common = { temperature, maxTokens, reasoningEffort };
  const [pickerOpen, setPickerOpen] = useState(false);
  const trigger = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    if (pickerOpen) return () => trigger.current?.focus();
  }, [pickerOpen]);
  const apply = (keys: string[]) => {
    replace(reconcileComparisons(getValues("comparisons"), keys));
    if (errors.comparisons) void validate("comparisons");
    setPickerOpen(false);
  };
  const duplicate = (index: number) => {
    const current = getValues("comparisons");
    const source = current[index];
    const choice = choices.find((item) => item.key === source?.modelKey);
    if (
      !source ||
      current.length >= MODEL_LIMITS.max ||
      !choice?.selectable ||
      !choice.tuningParameters?.length
    )
      return;
    const copy = createComparison(source.modelKey);
    copy.settings = {
      ...(source.settings.mode === "custom" ? source.settings : copy.settings),
      mode: "custom",
    };
    // 복제 칸은 모델별 설정이라, 체크박스로 켤 때와 같이 공통 설정을 끈다.
    setValue("commonEnabled", false, { shouldDirty: true });
    append(copy, { shouldFocus: false });
  };
  // 빈 칸 수는 최대 4개로 고정이라 자리 이름을 키로 쓴다
  const emptySlotKeys = EMPTY_SLOT_KEYS.slice(
    0,
    Math.max(0, MODEL_LIMITS.max - fields.length),
  );
  const emptySlot = (first: boolean) => (
    <button
      type="button"
      disabled={unavailable}
      onClick={() => setPickerOpen(true)}
      className="flex min-h-60 w-full flex-col items-center justify-center gap-2 rounded-xl border border-dashed border-grey-300 bg-grey-50 p-4 text-body-sm font-semibold text-grey-700 hover:bg-grey-100 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand disabled:cursor-not-allowed disabled:opacity-50"
    >
      <span
        aria-hidden="true"
        className="grid size-9 place-items-center rounded-full border border-grey-200 bg-white"
      >
        <Icon src={plusIcon} className="size-4" />
      </span>
      모델 추가
      {first && (
        <span className="text-caption font-normal text-grey-600">
          검색하거나 즐겨찾기에서 골라요 · 최대 {MODEL_LIMITS.max}개
        </span>
      )}
    </button>
  );
  return (
    <section className="flex flex-col gap-4 rounded-2xl bg-white p-6">
      <StepHeading number={2} title="어떤 모델을 비교할까요">
        <Badge tone="grey">{`${comparisons.length} / ${MODEL_LIMITS.max} 선택`}</Badge>
        <Button
          ref={trigger}
          size="sm"
          variant="secondary"
          icon={searchIcon}
          className="ml-auto"
          disabled={unavailable}
          aria-haspopup="dialog"
          onClick={() => setPickerOpen(true)}
        >
          모델 검색
        </Button>
      </StepHeading>
      <p className="text-caption text-grey-600">
        모델 카드의 설정이 실제로 전송돼요. 개별 설정이 공통 설정보다 우선하고,
        둘 다 비우면 시나리오·모델 기본값 순으로 써요.
      </p>
      {settings}
      {notice}
      {fields.length ? (
        // 빈 칸은 목록 항목이 아니라서 ul 밖에 두고, contents로 같은 격자에 올린다
        <div className="grid grid-cols-4 gap-3">
          <ul aria-label="선택한 비교 모델" className="contents">
            {fields.map((field, index) => (
              <ModelComparisonCard
                key={field.id}
                index={index}
                choice={choices.find(
                  (item) => item.key === comparisons[index]?.modelKey,
                )}
                comparison={comparisons[index] ?? field}
                common={common}
                scenario={scenario}
                hasImages={hasImages}
                hasSchema={hasSchema}
                imageOutput={imageOutput}
                count={comparisons.length}
                onRemove={() => remove(index)}
                onDuplicate={() => duplicate(index)}
              />
            ))}
          </ul>
          {emptySlotKeys.map((slotKey) => (
            <div key={slotKey} className="min-w-0">
              {emptySlot(false)}
            </div>
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-4 gap-3">
          {emptySlotKeys.map((slotKey, index) => (
            <div key={slotKey} className="min-w-0">
              {emptySlot(index === 0)}
            </div>
          ))}
        </div>
      )}
      <FieldError
        id="sim-comparisons-error"
        message={
          errors.comparisons?.root?.message ?? errors.comparisons?.message
        }
      />
      {pickerOpen && (
        <ModelPickerDialog
          choices={choicesForOutput(choices, outputType ?? "TEXT")}
          selections={comparisons.map((item) => item.modelKey)}
          counts={comparisonCounts(comparisons)}
          unavailable={unavailable}
          favorites={favorites}
          imagesAttached={hasImages}
          onClose={() => setPickerOpen(false)}
          onApply={apply}
        />
      )}
    </section>
  );
}
