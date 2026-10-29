import type { ComponentProps } from "react";
import { Icon } from "./Icon";

const VARIANT_CLASS = {
  primary: "bg-brand text-white hover:bg-blue-600",
  secondary: "bg-grey-100 text-grey-700 hover:bg-grey-200",
} as const;

// TDS Button M(38px)과 S(32px)
const SIZE_CLASS = {
  md: "h-9.5 gap-1.5 rounded-control px-4 text-body",
  sm: "h-8 gap-1 rounded-lg px-2.5 text-label",
} as const;

type ButtonProps = ComponentProps<"button"> & {
  variant?: keyof typeof VARIANT_CLASS;
  size?: keyof typeof SIZE_CLASS;
  /** 글자 앞에 붙는 아이콘(import한 SVG) */
  icon?: string;
};

export function Button({
  variant = "primary",
  size = "md",
  icon,
  type = "button",
  className = "",
  children,
  ...props
}: ButtonProps) {
  return (
    <button
      type={type}
      className={`inline-flex shrink-0 items-center justify-center font-semibold transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand disabled:cursor-not-allowed disabled:opacity-40 ${VARIANT_CLASS[variant]} ${SIZE_CLASS[size]} ${className}`}
      {...props}
    >
      {icon && <Icon src={icon} className="size-4" />}
      {children}
    </button>
  );
}
