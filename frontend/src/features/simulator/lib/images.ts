import { z } from "zod";
import { IMAGE_LIMITS, type ImageLimits } from "./limits";

export function imageCountMessage(limits: ImageLimits) {
  return `이미지는 최대 ${limits.maxCount}개까지 선택할 수 있습니다.`;
}

// 선택 직후와 제출 직전에 같은 정책으로 검사한다. 실제 파일 내용 검증은 서버의 책임이다.
export function imageFilesSchemaFor(limits: ImageLimits) {
  return z
    .array(
      z
        .instanceof(File)
        .refine(
          (file) => limits.mimeTypes.some((type) => type === file.type),
          "JPG·PNG·WebP 파일을 선택하시기 바랍니다.",
        )
        .refine(
          (file) => file.size > 0 && file.size <= limits.maxBytes,
          `빈 파일은 사용할 수 없습니다. 파일당 ${limits.maxBytes / 1024 / 1024}MiB 이하로 선택하시기 바랍니다.`,
        ),
    )
    .max(limits.maxCount, imageCountMessage(limits));
}

export const imageFilesSchema = imageFilesSchemaFor(IMAGE_LIMITS);

export function fileKey(file: File) {
  return `${file.name}:${file.size}:${file.lastModified}:${file.type}`;
}
