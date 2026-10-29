// TDS Badge S(24px)의 Weak 형태. 상태별 색은 docs/design/tokens.md "상태 배지"
const TONE_CLASS = {
  green: "bg-success-weak text-green-700",
  blue: "bg-brand-weak text-blue-600",
  yellow: "bg-warning-weak text-yellow-900",
  red: "bg-danger-weak text-red-600",
  grey: "bg-neutral-weak text-grey-700",
} as const;

type BadgeProps = {
  tone: keyof typeof TONE_CLASS;
  children: string;
};

export function Badge({ tone, children }: BadgeProps) {
  return (
    <span
      className={`inline-flex h-6 shrink-0 items-center whitespace-nowrap rounded-full px-1.75 text-caption font-bold ${TONE_CLASS[tone]}`}
    >
      {children}
    </span>
  );
}
