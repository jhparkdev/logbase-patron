import { type Control, Controller } from "react-hook-form";
import type { HistoryOption } from "../lib/presentation";
import type { HistoryFilters } from "../lib/search";

export function HistoryFilterSelect({
  control,
  name,
  label,
  options,
  className,
  allValue = "",
}: {
  control: Control<HistoryFilters>;
  name: "scenario" | "model" | "status";
  label: string;
  options: readonly HistoryOption[];
  className: string;
  allValue?: string;
}) {
  const id = useId();
  return (
    <label htmlFor={id} className="text-label text-grey-600">
      {label}
      <Controller
        control={control}
        name={name}
        render={({ field }) => (
          <select {...field} id={id} className={className}>
            <option value={allValue}>전체</option>
            {field.value !== allValue &&
              !options.some((item) => item.key === field.value) && (
                <option value={field.value}>선택한 {label}</option>
              )}
            {options.map((item) => (
              <option key={item.key} value={item.key}>
                {item.name}
              </option>
            ))}
          </select>
        )}
      />
    </label>
  );
}

import { useId } from "react";
