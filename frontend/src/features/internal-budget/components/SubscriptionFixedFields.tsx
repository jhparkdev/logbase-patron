import type { SubscriptionFormValues } from "../lib/forms";

const FIELDS = [
  { key: "reference", label: "구독 식별값" },
  { key: "toolName", label: "도구명" },
  { key: "type", label: "구독 종류" },
  { key: "month", label: "적용 월" },
] as const;

/** 등록 뒤 바꿀 수 없는 값. 수정 폼에서는 입력 칸 대신 글자로 보여 준다. */
export function SubscriptionFixedFields({
  values,
}: {
  values: SubscriptionFormValues;
}) {
  return (
    <dl className="grid grid-cols-2 gap-2">
      {FIELDS.map((field) => (
        <div
          key={field.key}
          className="flex flex-col gap-1 rounded-xl bg-grey-50 p-3"
        >
          <dt className="text-caption text-grey-600">{field.label}</dt>
          <dd className="font-bold">
            {values[field.key] === "" ? (
              <span className="font-normal text-grey-600">없음</span>
            ) : (
              values[field.key]
            )}
          </dd>
        </div>
      ))}
    </dl>
  );
}
