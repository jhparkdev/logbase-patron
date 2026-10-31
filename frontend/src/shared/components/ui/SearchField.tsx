import { useEffect, useRef } from "react";
import searchIcon from "../../../assets/search.svg";
import { FIELD_CLASS } from "./fieldStyle";
import { Icon } from "./Icon";

/** 입력이 이만큼 멈추면 검색한다. 글자마다 요청하지 않기 위해서다. */
export const SEARCH_DELAY_MS = 300;

type SearchFieldProps = {
  label: string;
  placeholder: string;
  /** 지금 적용된 검색어(주소의 값) */
  value?: string;
  onSearch: (text: string) => void;
};

export function SearchField({
  label,
  placeholder,
  value = "",
  onSearch,
}: SearchFieldProps) {
  const input = useRef<HTMLInputElement>(null);
  const timer = useRef<ReturnType<typeof setTimeout>>(undefined);
  useEffect(() => () => clearTimeout(timer.current), []);

  // 뒤로 가기처럼 검색어가 바깥에서 바뀔 때만 입력창을 맞춘다.
  // 직접 입력한 글자로 검색한 경우는 같은 값이라 입력 중인 공백을 지우지 않는다.
  useEffect(() => {
    if (input.current && input.current.value.trim() !== value) {
      input.current.value = value;
    }
  }, [value]);

  return (
    <div className="relative min-w-0 flex-1">
      <Icon
        src={searchIcon}
        className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-grey-500"
      />
      <input
        ref={input}
        type="search"
        aria-label={label}
        placeholder={placeholder}
        defaultValue={value}
        onChange={(event) => {
          const text = event.target.value;
          clearTimeout(timer.current);
          timer.current = setTimeout(
            () => onSearch(text.trim()),
            SEARCH_DELAY_MS,
          );
        }}
        className={`${FIELD_CLASS} w-full pr-3 pl-9 placeholder:text-grey-500`}
      />
    </div>
  );
}
