import { useId } from "react";
import dropDownIcon from "../../../assets/dropDown.svg";
import { FIELD_CLASS } from "./fieldStyle";
import { Icon } from "./Icon";

type SelectProps = {
  /** 선택 상자의 이름. 예: Provider */
  label: string;
  /** 이름을 보여 줄 자리. hidden이면 화면 낭독기만 읽는다. side는 한 줄 조회 조건에서 쓴다. */
  labelPosition?: keyof typeof LABEL_LAYOUT_CLASS | "hidden";
  value: string;
  /** "전체" 같은 기본 항목도 여기에 넣는다(값은 빈 문자열). */
  options: { value: string; label: string }[];
  onChange: (value: string) => void;
  disabled?: boolean;
  /** 상자 너비처럼 놓이는 자리에서 정할 값. 예: w-56 */
  className?: string;
};

const LABEL_LAYOUT_CLASS = {
  top: "flex flex-col gap-1.5",
  side: "flex items-center gap-2",
};

/**
 * 브라우저 기본 select에 모양만 입힌다. 펼친 목록은 운영체제가 그린다.
 * 검색이나 그림이 든 항목이 필요해지면 이 컴포넌트 안쪽만 바꾼다.
 */
export function Select({
  label,
  labelPosition = "hidden",
  value,
  options,
  onChange,
  disabled = false,
  className = "",
}: SelectProps) {
  const selectId = useId();
  const box = (
    <div className={`relative shrink-0 ${className}`}>
      <select
        id={selectId}
        aria-label={labelPosition === "hidden" ? label : undefined}
        value={value}
        disabled={disabled}
        onChange={(event) => onChange(event.target.value)}
        className={`${FIELD_CLASS} w-full appearance-none pr-9 pl-3 disabled:cursor-not-allowed disabled:opacity-60`}
      >
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
      <Icon
        src={dropDownIcon}
        className="pointer-events-none absolute top-1/2 right-3 h-2 w-3 -translate-y-1/2 text-grey-600"
      />
    </div>
  );

  if (labelPosition === "hidden") {
    return box;
  }
  return (
    <div className={LABEL_LAYOUT_CLASS[labelPosition]}>
      <label
        htmlFor={selectId}
        className="text-label font-medium text-grey-700"
      >
        {label}
      </label>
      {box}
    </div>
  );
}
