import { useEffect, useRef, useState } from "react";
import { useFormContext, useWatch } from "react-hook-form";
import searchIcon from "../../../assets/search.svg";
import { Button } from "../../../shared/components/ui/Button";
import type { ModelFavoritesView } from "../lib/favorites";
import type { SimulatorDraft, SimulatorFormValues } from "../lib/form";
import { MODEL_LIMITS } from "../lib/limits";
import type { ModelChoice } from "../lib/presentation";
import { FieldError } from "./InputFields";
import { ModelCreatorBadge } from "./ModelCreatorBadge";
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
    setValue,
    formState: { errors },
  } = useFormContext<SimulatorFormValues, unknown, SimulatorDraft>();
  const selections = useWatch({ control, name: "selections" });
  const [pickerOpen, setPickerOpen] = useState(false);
  const trigger = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    if (!pickerOpen) return;
    return () => trigger.current?.focus();
  }, [pickerOpen]);
  const apply = (keys: string[]) => {
    setValue("selections", keys, {
      shouldDirty: true,
      shouldTouch: true,
      shouldValidate: !!errors.selections,
    });
    setPickerOpen(false);
  };
  return (
    <section className="border-t border-grey-100 pt-5">
      <div className="mb-3 flex flex-wrap items-center gap-3">
        <h3 className="text-label font-semibold">
          모델 선택{" "}
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
      {selections.length ? (
        <ul aria-label="선택한 비교 모델" className="grid grid-cols-2 gap-3">
          {selections.map((key, index) => {
            const selected = choices.find((item) => item.key === key);
            return (
              <li
                key={key}
                className="rounded-control border border-grey-200 p-3"
              >
                <div className="mb-2 flex items-center justify-between">
                  <h4 className="text-label font-semibold">
                    비교 모델 {index + 1}
                  </h4>
                  <Button
                    size="sm"
                    variant="secondary"
                    aria-label={`비교 모델 ${index + 1} 제거`}
                    disabled={selections.length === 1}
                    onClick={() =>
                      setValue(
                        "selections",
                        selections.filter((_, i) => i !== index),
                        {
                          shouldDirty: true,
                          shouldValidate: !!errors.selections,
                        },
                      )
                    }
                  >
                    제거
                  </Button>
                </div>
                <p className="text-body-sm font-semibold">
                  {selected?.name ?? "목록에 없는 모델"}
                </p>
                <div className="mt-2">
                  <ModelCreatorBadge creator={selected?.creator} />
                </div>
                {selected && (
                  <div className="mt-1 flex items-center gap-2 text-caption text-grey-600">
                    <span>{selected.provider}</span>
                    <span>
                      · {selected.supportsImages ? "텍스트·이미지" : "텍스트"}
                    </span>
                  </div>
                )}
                {selected && !selected.selectable && (
                  <p className="mt-1 text-caption text-red-600">
                    {selected.unavailableReason ?? "선택 불가"}
                  </p>
                )}
              </li>
            );
          })}
        </ul>
      ) : (
        <p className="rounded-control border border-dashed border-grey-200 p-5 text-body-sm text-grey-600">
          모델 검색에서 비교할 모델을 한 번에 선택하시기 바랍니다.
        </p>
      )}
      <FieldError
        id="sim-selections-error"
        message={errors.selections?.root?.message ?? errors.selections?.message}
      />
      {pickerOpen && (
        <ModelPickerDialog
          choices={choices}
          selections={selections}
          unavailable={unavailable}
          favorites={favorites}
          onClose={() => setPickerOpen(false)}
          onApply={apply}
        />
      )}
    </section>
  );
}
