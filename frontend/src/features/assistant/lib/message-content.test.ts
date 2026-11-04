import { expect, test } from "vitest";
import { parseMessageContent, requestsRawValues } from "./message-content";

test("formats dates inside emphasis and groups paragraphs and lists", () => {
  const blocks = parseMessageContent(
    "최근 호출은 **2026-11-02T07:11:38.580827Z**입니다.\n\n- 성공 1200건\n- 비용 미확인\n\n다음 안내",
  );
  expect(blocks.map((block) => block.kind)).toEqual([
    "paragraph",
    "list",
    "paragraph",
  ]);
  expect(blocks[0]).toMatchObject({
    content: [
      { kind: "text", value: "최근 호출은 " },
      { kind: "strong", value: "2026년 11월 2일 16:11:38 (한국시간)" },
      { kind: "text", value: "입니다." },
    ],
  });
  expect(blocks[1]).toMatchObject({
    ordered: false,
    items: [
      { content: [{ kind: "text", value: "성공 1,200건" }] },
      { content: [{ kind: "text", value: "비용 미확인" }] },
    ],
  });
});

test("code samples preserve timestamps, exact amounts and markup", () => {
  const source =
    '```json\n{"requested_at":"2026-11-02T07:11:38.580827Z","cost":"$1.230000000000"}\n```';
  expect(parseMessageContent(source)).toMatchObject([
    { kind: "code", value: source.split("\n")[1] },
  ]);
  expect(
    parseMessageContent("원문: `2026-11-02T07:11:38.580827Z`", true)[0],
  ).toMatchObject({
    content: [
      { kind: "text", value: "원문: " },
      { kind: "code", value: "2026-11-02T07:11:38.580827Z" },
    ],
  });
});

test("inline-code timestamps are readable unless original values were requested", () => {
  const source = "최근 시각: `2026-11-02T07:11:38.580827Z`";
  expect(parseMessageContent(source)[0]).toMatchObject({
    content: [
      { kind: "text", value: "최근 시각: " },
      { kind: "text", value: "2026년 11월 2일 16:11:38 (한국시간)" },
    ],
  });
  expect(
    parseMessageContent("원문: 2026-11-02T07:11:38.580827Z", true)[0],
  ).toMatchObject({
    content: [{ value: "원문: 2026-11-02T07:11:38.580827Z" }],
  });
  expect(requestsRawValues("가장 최근 요청 시각을 알려줘")).toBe(false);
  expect(requestsRawValues("ISO 8601 원문으로 알려줘")).toBe(true);
  expect(requestsRawValues("JSON의 정확한 금액을 보여줘")).toBe(true);
});

test("headings, ordered lists and unfinished markup remain readable", () => {
  expect(parseMessageContent("### 결과\n3. 첫 번째\n4. 두 번째")).toMatchObject(
    [{ kind: "heading" }, { kind: "list", ordered: true, start: 3 }],
  );
  expect(parseMessageContent('```json\n{"unfinished":true}')).toMatchObject([
    { kind: "code", value: '{"unfinished":true}' },
  ]);
  expect(parseMessageContent("**미완성 강조")).toMatchObject([
    { content: [{ kind: "text", value: "**미완성 강조" }] },
  ]);
});
