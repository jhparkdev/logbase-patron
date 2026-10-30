// UI 단계의 입력 정책. 서버 계약이 생기면 이 값을 계약에서 공급받는다.
export const TEXT_LIMIT = 2_000;
export const MODEL_LIMITS = { min: 2, max: 4 } as const;
export const IMAGE_LIMITS = {
  mimeTypes: ["image/jpeg", "image/png", "image/webp"],
  maxCount: 4,
  maxBytes: 5 * 1024 * 1024,
} as const;

// OpenRouter 공식 Parameters 문서(2026-10-29). 모델별 지원 여부는 별도로 확인한다.
export const TEMPERATURE = {
  min: 0,
  max: 2,
  step: 0.01,
  sliderStart: 1,
} as const;
export const controlClass =
  "w-full rounded-control border border-grey-200 bg-grey-50 px-3 py-2 text-body-sm text-grey-900 focus:border-brand focus:outline-2 focus:outline-offset-2 focus:outline-brand disabled:cursor-not-allowed disabled:opacity-50 aria-invalid:border-red-500";
