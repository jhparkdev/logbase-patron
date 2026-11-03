import type { CapabilityTag } from "../lib/capabilities";

// 규격은 docs/design/tokens.md "지원 기능 태그"
const TAG_CLASS = {
  supported: "bg-brand-weak text-blue-600",
  unsupported: "bg-neutral-weak text-grey-600",
} as const;
const MARK = { supported: "✓", unsupported: "✕" } as const;
const UNSUPPORTED_LABEL = "미지원";

/** 지원 기능 태그 묶음. 색과 기호에 더해 글자(화면 낭독기)로도 미지원을 알림 */
export function CapabilityTags({ tags }: { tags: CapabilityTag[] }) {
  return (
    <ul aria-label="지원 기능" className="flex flex-wrap gap-1.5">
      {tags.map((tag) => {
        const state = tag.supported ? "supported" : "unsupported";
        return (
          <li
            key={tag.key}
            className={`inline-flex h-6 items-center gap-1 whitespace-nowrap rounded-full px-2 text-caption font-semibold ${TAG_CLASS[state]}`}
          >
            <span aria-hidden="true">{MARK[state]}</span>
            <span>{tag.label}</span>
            {!tag.supported && (
              <span className="sr-only">{UNSUPPORTED_LABEL}</span>
            )}
          </li>
        );
      })}
    </ul>
  );
}
