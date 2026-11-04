import { formatAssistantProse } from "../../../shared/lib/assistant-format";

export type MessageInline = {
  key: number;
  kind: "text" | "strong" | "code";
  value: string;
};
export type MessageBlock =
  | { key: number; kind: "paragraph" | "heading"; content: MessageInline[] }
  | {
      key: number;
      kind: "list";
      ordered: boolean;
      start: number;
      items: { key: number; content: MessageInline[] }[];
    }
  | { key: number; kind: "code"; value: string };

const FENCE = /^\s*```[\w+-]*\s*$/;
const HEADING = /^#{1,3}\s+(.+)$/;
const LIST = /^\s*(?:([-*])|(\d+)[.)])\s+(.+)$/;

/** 원시 값이나 특정 시간대 요청은 읽기 쉬운 표시보다 원문 보존을 우선한다. */
export function requestsRawValues(request: string): boolean {
  return /원문|원시|\b(?:raw|iso|json|utc)\b|타임스탬프|밀리초|마이크로초/i.test(
    request,
  );
}

function inline(content: string, rawValues: boolean): MessageInline[] {
  const format = rawValues ? (value: string) => value : formatAssistantProse;
  const result: MessageInline[] = [];
  let cursor = 0;
  for (const match of content.matchAll(/`([^`\n]+)`|\*\*([^*\n]+)\*\*/g)) {
    if (match.index > cursor)
      result.push({
        key: cursor,
        kind: "text",
        value: format(content.slice(cursor, match.index)),
      });
    const readableTime =
      match[1] && /^\d{4}-\d{2}-\d{2}T/.test(match[1])
        ? format(match[1])
        : undefined;
    result.push({
      key: match.index,
      kind:
        match[1] === undefined
          ? "strong"
          : readableTime !== undefined && readableTime !== match[1]
            ? "text"
            : "code",
      value: readableTime ?? match[1] ?? format(match[2]),
    });
    cursor = match.index + match[0].length;
  }
  if (cursor < content.length)
    result.push({
      key: cursor,
      kind: "text",
      value: format(content.slice(cursor)),
    });
  return result;
}

/** 제한된 강조·목록·문단·코드 구문만 읽는다. HTML과 외부 링크는 실행하지 않는다. */
export function parseMessageContent(
  content: string,
  rawValues = false,
): MessageBlock[] {
  const lines = content.replace(/\r\n/g, "\n").split("\n");
  const blocks: MessageBlock[] = [];
  let cursor = 0;
  while (cursor < lines.length) {
    const key = cursor;
    const line = lines[cursor];
    if (!line.trim()) {
      cursor += 1;
      continue;
    }
    if (FENCE.test(line)) {
      const code: string[] = [];
      cursor += 1;
      while (cursor < lines.length && !FENCE.test(lines[cursor])) {
        code.push(lines[cursor]);
        cursor += 1;
      }
      if (cursor < lines.length) cursor += 1;
      blocks.push({ key, kind: "code", value: code.join("\n") });
      continue;
    }
    const heading = HEADING.exec(line);
    if (heading) {
      blocks.push({
        key,
        kind: "heading",
        content: inline(heading[1], rawValues),
      });
      cursor += 1;
      continue;
    }
    const item = LIST.exec(line);
    if (item) {
      const ordered = item[2] !== undefined;
      const items: { key: number; content: MessageInline[] }[] = [];
      while (cursor < lines.length) {
        const next = LIST.exec(lines[cursor]);
        if (!next || (next[2] !== undefined) !== ordered) break;
        items.push({ key: cursor, content: inline(next[3], rawValues) });
        cursor += 1;
      }
      blocks.push({
        key,
        kind: "list",
        ordered,
        start: ordered ? Number(item[2]) : 1,
        items,
      });
      continue;
    }
    const paragraph = [line];
    cursor += 1;
    while (
      cursor < lines.length &&
      lines[cursor].trim() &&
      !FENCE.test(lines[cursor]) &&
      !HEADING.test(lines[cursor]) &&
      !LIST.test(lines[cursor])
    ) {
      paragraph.push(lines[cursor]);
      cursor += 1;
    }
    blocks.push({
      key,
      kind: "paragraph",
      content: inline(paragraph.join("\n"), rawValues),
    });
  }
  return blocks;
}
