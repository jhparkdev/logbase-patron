import { expect, test } from "vitest";
import { existingImageLabel } from "./images";

test("기존 이미지는 원래 파일 이름으로 부르고, 이름을 모르면 순서로 부른다", () => {
  const names = { a: "receipt.png" };
  expect(existingImageLabel("a", 0, names)).toBe("receipt.png");
  expect(existingImageLabel("b", 1, names)).toBe("기존 이미지 2");
});
