import dropDownIcon from "../../../assets/dropDown.svg";
import { Icon } from "./Icon";

type SelectProps = {
  /** 화면 낭독기가 읽는 이름. 예: Provider */
  label: string;
  value: string;
  /** "전체" 같은 기본 항목도 여기에 넣는다(값은 빈 문자열). */
  options: { value: string; label: string }[];
  onChange: (value: string) => void;
  disabled?: boolean;
  /** 너비처럼 놓이는 자리에서 정할 값. 예: w-56 */
  className?: string;
};

/**
 * 브라우저 기본 select에 모양만 입힌다. 펼친 목록은 운영체제가 그린다.
 * 검색이나 그림이 든 항목이 필요해지면 이 컴포넌트 안쪽만 바꾼다.
 */
export function Select({
  label,
  value,
  options,
  onChange,
  disabled = false,
  className = "",
}: SelectProps) {
  return (
    <div className={`relative shrink-0 ${className}`}>
      <select
        aria-label={label}
        value={value}
        disabled={disabled}
        onChange={(event) => onChange(event.target.value)}
        className="h-9.5 w-full appearance-none rounded-control border border-neutral-weak bg-grey-50 pr-9 pl-3 text-body-sm focus-visible:border-brand focus-visible:outline-none disabled:cursor-not-allowed disabled:opacity-60"
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
}
