import { useEffect, useRef, useState } from "react";
import { useFieldArray, useFormContext, useWatch } from "react-hook-form";
import searchIcon from "../../../assets/search.svg";
import { Button } from "../../../shared/components/ui/Button";
import {
  comparisonCounts,
  createComparison,
  reconcileComparisons,
} from "../lib/comparisons";
import type { ModelFavoritesView } from "../lib/favorites";
import type { SimulatorDraft, SimulatorFormValues } from "../lib/form";
import { MODEL_LIMITS } from "../lib/limits";
import type { ModelChoice } from "../lib/presentation";
import { FieldError } from "./InputFields";
import { ModelComparisonCard } from "./ModelComparisonCard";
import { ModelPickerDialog } from "./ModelPickerDialog";

export function ModelSelection({
  choices,
  unavailable,
  favorites,
}: {
  choices: ModelChoice[];
  unavailable: boolean;
  favorites?: ModelFavoritesView;
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
  const comparisons = useWatch({ control, name: "comparisons" });
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
  return (
    <section className="border-t border-grey-100 pt-5">
      <div className="mb-3 flex flex-wrap items-center gap-3">
        <h3 className="text-label font-semibold">
          비교 항목{" "}
          <span className="font-normal text-grey-600">
            ({MODEL_LIMITS.min}~{MODEL_LIMITS.max}개)
          </span>
        </h3>
        <Button
          ref={trigger}
          size="sm"
          variant="secondary"
          icon={searchIcon}
          disabled={unavailable}
          aria-haspopup="dialog"
          onClick={() => setPickerOpen(true)}
        >
          모델 검색
        </Button>
      </div>
      {comparisons.length === 1 && (
        <p className="mb-3 text-caption text-grey-600">
          모델을 추가하거나 ‘다른 설정으로 비교’로 복제하면 비교할 수 있습니다.
        </p>
      )}
      {fields.length ? (
        <ul aria-label="선택한 비교 모델" className="grid grid-cols-2 gap-3">
          {fields.map((field, index) => (
            <ModelComparisonCard
              key={field.id}
              index={index}
              choice={choices.find(
                (item) => item.key === comparisons[index]?.modelKey,
              )}
              count={comparisons.length}
              onRemove={() => remove(index)}
              onDuplicate={() => duplicate(index)}
            />
          ))}
        </ul>
      ) : (
        <p className="rounded-control border border-dashed border-grey-200 p-5 text-body-sm text-grey-600">
          모델 검색에서 비교할 모델을 한 번에 선택하시기 바랍니다.
        </p>
      )}
      <FieldError
        id="sim-comparisons-error"
        message={
          errors.comparisons?.root?.message ?? errors.comparisons?.message
        }
      />
      {pickerOpen && (
        <ModelPickerDialog
          choices={choices}
          selections={comparisons.map((item) => item.modelKey)}
          counts={comparisonCounts(comparisons)}
          unavailable={unavailable}
          favorites={favorites}
          onClose={() => setPickerOpen(false)}
          onApply={apply}
        />
      )}
    </section>
  );
}
