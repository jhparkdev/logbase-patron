import { z } from "zod";
import { IMAGE_LIMITS } from "./limits";

// 선택 직후와 제출 직전에 같은 정책으로 검사한다. 실제 파일 내용 검증은 서버의 책임이다.
export const imageFilesSchema = z
  .array(
    z
      .instanceof(File)
      .refine(
        (file) => IMAGE_LIMITS.mimeTypes.some((type) => type === file.type),
        "JPG·PNG·WebP 파일을 선택해 주세요.",
      )
      .refine(
        (file) => file.size > 0 && file.size <= IMAGE_LIMITS.maxBytes,
        `빈 파일은 사용할 수 없어요. 파일당 ${IMAGE_LIMITS.maxBytes / 1024 / 1024}MiB 이하로 선택해 주세요.`,
      ),
  )
  .max(
    IMAGE_LIMITS.maxCount,
    `이미지는 최대 ${IMAGE_LIMITS.maxCount}개까지 선택할 수 있어요.`,
  );

export function fileKey(file: File) {
  return `${file.name}:${file.size}:${file.lastModified}:${file.type}`;
}
