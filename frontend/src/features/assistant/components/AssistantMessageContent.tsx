import {
  type MessageInline,
  parseMessageContent,
} from "../lib/message-content";

function InlineContent({ content }: { content: MessageInline[] }) {
  return content.map((part) => {
    if (part.kind === "strong")
      return (
        <strong key={part.key} className="font-semibold text-grey-900">
          {part.value}
        </strong>
      );
    if (part.kind === "code")
      return (
        <code
          key={part.key}
          className="rounded bg-grey-100 px-1 py-0.5 font-mono text-label"
        >
          {part.value}
        </code>
      );
    return <span key={part.key}>{part.value}</span>;
  });
}

export function AssistantMessageContent({
  content,
  rawValues = false,
}: {
  content: string;
  rawValues?: boolean;
}) {
  return (
    <div className="space-y-3 whitespace-pre-wrap wrap-anywhere text-grey-800">
      {parseMessageContent(content, rawValues).map((block) => {
        if (block.kind === "code")
          return (
            <pre
              key={block.key}
              className="overflow-x-auto rounded-lg bg-grey-100 p-3 whitespace-pre font-mono text-label"
            >
              <code>{block.value}</code>
            </pre>
          );
        if (block.kind === "list") {
          const items = block.items.map((item) => (
            <li key={item.key} className="pl-1">
              <InlineContent content={item.content} />
            </li>
          ));
          return block.ordered ? (
            <ol
              key={block.key}
              start={block.start}
              className="list-decimal space-y-2 pl-5"
            >
              {items}
            </ol>
          ) : (
            <ul key={block.key} className="list-disc space-y-2 pl-5">
              {items}
            </ul>
          );
        }
        return (
          <p
            key={block.key}
            className={
              block.kind === "heading"
                ? "font-semibold text-grey-900"
                : undefined
            }
          >
            <InlineContent content={block.content} />
          </p>
        );
      })}
    </div>
  );
}
