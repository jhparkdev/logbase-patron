import type { ModelChoice } from "../lib/presentation";
import { supportsStructuredOutput } from "../lib/presentation";

const TAG_CLASS = {
  supported: "bg-brand-weak text-blue-600",
  unsupported: "bg-neutral-weak text-grey-600",
  // 입력과 맞지 않아 실행이 막히는 미지원
  conflict: "bg-danger-weak text-red-600",
} as const;

function SupportTag({
  label,
  supported,
  conflict,
}: {
  label: string;
  supported: boolean;
  conflict: boolean;
}) {
  const kind = supported ? "supported" : conflict ? "conflict" : "unsupported";
  return (
    <span
      className={`inline-flex h-6 items-center gap-1 rounded-full px-2 text-caption font-semibold whitespace-nowrap ${TAG_CLASS[kind]}`}
    >
      <span aria-hidden="true">{supported ? "✓" : "✕"}</span>
      {label}
      {!supported && <span className="sr-only"> 미지원</span>}
    </span>
  );
}

/** 모델이 이미지 입력과 JSON Schema 출력을 지원하는지. 입력과 어긋나면 빨갛게 표시한다. */
export function SupportTags({
  choice,
  hasImages = false,
  hasSchema = false,
  showSchema = true,
}: {
  choice: ModelChoice;
  hasImages?: boolean;
  hasSchema?: boolean;
  // 이미지 생성 실행은 Schema를 보내지 않아 JSON 지원 여부가 의미 없다
  showSchema?: boolean;
}) {
  return (
    <div className="flex flex-wrap gap-1.5">
      <SupportTag
        label="이미지"
        supported={choice.supportsImages}
        conflict={hasImages}
      />
      {showSchema && (
        <SupportTag
          label="JSON"
          supported={supportsStructuredOutput(choice)}
          conflict={hasSchema}
        />
      )}
    </div>
  );
}
