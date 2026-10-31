import { selectedComparisonCount } from "./comparisons";
import { MODEL_LIMITS } from "./limits";
import type { ModelChoice } from "./presentation";

export function selectedModelKeys(selections: string[]) {
  return [...new Set(selections.filter(Boolean))];
}

export function searchModels(choices: ModelChoice[], query: string) {
  const terms = query.trim().toLocaleLowerCase().split(/\s+/);
  return choices.filter((choice) => {
    const label =
      `${choice.name} ${choice.creator ?? ""} ${choice.provider}`.toLocaleLowerCase();
    return terms.every((term) => label.includes(term));
  });
}

export function canApplyModels(
  selections: string[],
  choices: ModelChoice[],
  counts: Readonly<Record<string, number>> = {},
) {
  const count = selectedComparisonCount(selections, counts);
  return (
    count >= 1 &&
    count <= MODEL_LIMITS.max &&
    new Set(selections).size === selections.length &&
    selections.every((key) =>
      choices.some((choice) => choice.key === key && choice.selectable),
    )
  );
}
