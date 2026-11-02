import type { UseFormRegisterReturn } from "react-hook-form";

const STATUS_OPTIONS = [
  { value: "ACTIVE", label: "사용 중" },
  { value: "CANCELLED", label: "해지" },
] as const;

/** 사용 중 / 해지 두 칸 토글. 수정 폼에서만 쓴다(등록은 서버가 "사용 중"으로 저장). */
export function SubscriptionStatusField({
  field,
}: {
  field: UseFormRegisterReturn;
}) {
  return (
    <fieldset>
      <legend className="mb-1.5 text-label font-medium text-grey-700">
        상태
      </legend>
      <div className="grid grid-cols-2 gap-1 rounded-xl bg-grey-100 p-1">
        {STATUS_OPTIONS.map((option) => (
          <label
            key={option.value}
            className="flex h-9 cursor-pointer items-center justify-center rounded-lg text-body-sm font-medium text-grey-600 has-checked:bg-white has-checked:font-semibold has-checked:text-grey-900 has-focus-visible:outline-2 has-focus-visible:outline-brand"
          >
            <input
              type="radio"
              value={option.value}
              className="sr-only"
              {...field}
            />
            {option.label}
          </label>
        ))}
      </div>
    </fieldset>
  );
}
