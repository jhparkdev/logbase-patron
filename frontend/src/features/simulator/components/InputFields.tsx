import { useState } from "react";
import { useFormContext, useWatch } from "react-hook-form";
import { Badge } from "../../../shared/components/ui/Badge";
import { formatCount } from "../../../shared/lib/format";
import { useImageSelection } from "../hooks/useImageSelection";
import type { SimulatorDraft, SimulatorFormValues } from "../lib/form";
import { existingImageLabel, fileKey } from "../lib/images";
import { controlClass, type ImageLimits, TEXT_LIMIT } from "../lib/limits";
import type { ScenarioChoice } from "../lib/presentation";
import { OutputTypeField } from "./OutputTypeField";
import { StepHeading } from "./StepHeading";

type Extra = "text" | "images" | "schema";
const EXTRAS: readonly { key: Extra; label: string }[] = [
  { key: "text", label: "입력 텍스트" },
  { key: "images", label: "이미지" },
  { key: "schema", label: "JSON Schema" },
];
const MODES = [
  { value: "custom", label: "직접 입력" },
  { value: "scenario", label: "기본 시나리오" },
] as const;

export function InputFields({
  scenarios,
  imageLimits,
}: {
  scenarios: ScenarioChoice[];
  imageLimits: ImageLimits;
}) {
  const { selectFiles, removeFile, removeExisting } =
    useImageSelection(imageLimits);
  const {
    register,
    control,
    setValue,
    formState: { errors },
  } = useFormContext<SimulatorFormValues, unknown, SimulatorDraft>();
  const [
    mode,
    prompt,
    text,
    files,
    existingAssetIds,
    existingImageNames,
    jsonSchema,
  ] = useWatch({
    control,
    name: [
      "mode",
      "prompt",
      "text",
      "files",
      "existingAssetIds",
      "existingImageNames",
      "jsonSchema",
    ],
  });
  const fileError =
    errors.files?.message ??
    errors.files?.root?.message ??
    files.map((_, index) => errors.files?.[index]?.message).find(Boolean);
  const imageCount = files.length + existingAssetIds.length;
  // 내용이나 오류가 있는 항목은 닫을 수 없다. 숨긴 채로 제출되는 값이 없게 하기 위해서다.
  const [opened, setOpened] = useState<Record<Extra, boolean>>({
    text: false,
    images: false,
    schema: false,
  });
  const locked: Record<Extra, boolean> = {
    text: text.length > 0 || !!errors.text,
    images: imageCount > 0 || !!fileError,
    schema: jsonSchema.length > 0 || !!errors.jsonSchema,
  };
  const isOpen = (key: Extra) => opened[key] || locked[key];
  const chipDetail: Record<Extra, string> = {
    text: text.length ? `${formatCount(Array.from(text).length)}자` : "",
    images: imageCount ? `${formatCount(imageCount)}장` : "",
    schema: jsonSchema.length ? "있음" : "",
  };
  const applyScenario = (key: string) => {
    setValue("scenarioKey", key);
    const scenario = scenarios.find((item) => item.key === key);
    if (!scenario) return;
    setValue("prompt", scenario.prompt);
    setValue("jsonSchema", scenario.schemaText);
    setValue("temperature", "");
    setValue("maxTokens", "");
  };
  return (
    <section className="flex flex-col gap-5 rounded-2xl bg-white p-6">
      <StepHeading number={1} title="무엇을 테스트할까요">
        <fieldset className="ml-auto flex rounded-xl bg-grey-100 p-1">
          <legend className="sr-only">테스트 유형</legend>
          {MODES.map((option) => (
            <label
              key={option.value}
              className="flex h-9 cursor-pointer items-center rounded-lg px-3.5 text-label font-semibold text-grey-600 has-checked:bg-white has-checked:text-grey-900 has-checked:shadow-sm has-disabled:cursor-not-allowed has-disabled:text-grey-400 has-focus-visible:outline-2 has-focus-visible:outline-brand"
            >
              <input
                {...register("mode")}
                type="radio"
                value={option.value}
                disabled={option.value === "scenario" && !scenarios.length}
                className="sr-only"
              />
              {option.label}
            </label>
          ))}
        </fieldset>
      </StepHeading>
      {mode === "scenario" && (
        <div>
          <label
            htmlFor="sim-scenario"
            className="mb-2 block text-label font-semibold"
          >
            시나리오
          </label>
          <select
            {...register("scenarioKey")}
            onChange={(event) => applyScenario(event.target.value)}
            id="sim-scenario"
            aria-invalid={!!errors.scenarioKey}
            aria-describedby="sim-scenario-error"
            className={controlClass}
          >
            <option value="">시나리오를 골라 주세요</option>
            {scenarios.map((item) => (
              <option key={item.key} value={item.key}>
                {item.name}
                {item.imageRequired ? "(이미지 필요)" : ""}
              </option>
            ))}
          </select>
          <FieldError
            id="sim-scenario-error"
            message={errors.scenarioKey?.message}
          />
        </div>
      )}
      <div>
        <div className="mb-2 flex items-baseline justify-between gap-2">
          <div className="flex items-center gap-1.5">
            <label htmlFor="sim-prompt" className="text-label font-semibold">
              Prompt
            </label>
            <Badge tone="red">필수</Badge>
          </div>
          <span className="text-caption text-grey-600">
            모델에게 시킬 작업을 적어요
          </span>
        </div>
        <textarea
          {...register("prompt")}
          id="sim-prompt"
          rows={6}
          placeholder="예: 다음 상품 설명을 읽고 소재, 계절, 추천 착용 상황을 JSON으로 정리해 주세요."
          aria-invalid={!!errors.prompt}
          aria-describedby="sim-prompt-count sim-prompt-error"
          className={`${controlClass} resize-y`}
        />
        <CharacterCount id="sim-prompt-count" value={prompt} />
        <FieldError id="sim-prompt-error" message={errors.prompt?.message} />
      </div>
      <div className="flex flex-col gap-3">
        <div className="flex flex-wrap items-center gap-2">
          <span className="mr-1 text-label font-semibold">추가 입력</span>
          {EXTRAS.map((extra) => {
            const open = isOpen(extra.key);
            return (
              <button
                key={extra.key}
                type="button"
                aria-pressed={open}
                title={
                  locked[extra.key] ? "내용이 있어서 닫을 수 없어요" : undefined
                }
                onClick={() => {
                  if (locked[extra.key]) return;
                  setOpened((previous) => ({
                    ...previous,
                    [extra.key]: !previous[extra.key],
                  }));
                }}
                className={`inline-flex h-8 items-center gap-1.5 rounded-full border px-3 text-label font-semibold focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand ${
                  open
                    ? "border-brand bg-blue-50 text-blue-600"
                    : "border-grey-200 bg-white text-grey-700 hover:bg-grey-50"
                }`}
              >
                <span aria-hidden="true">{open ? "✓" : "+"}</span>
                {extra.label}
                {chipDetail[extra.key] && (
                  <span className="font-normal tabular-nums">
                    {chipDetail[extra.key]}
                  </span>
                )}
              </button>
            );
          })}
          <span className="text-caption text-grey-600">
            켠 항목만 아래에 나와요. 모두 선택사항이에요.
          </span>
        </div>
        {(isOpen("text") || isOpen("images") || isOpen("schema")) && (
          <div className="grid grid-cols-2 gap-5">
            {isOpen("text") && (
              <div>
                <label
                  htmlFor="sim-text"
                  className="mb-2 block text-label font-semibold"
                >
                  입력 텍스트
                </label>
                <textarea
                  {...register("text")}
                  id="sim-text"
                  rows={4}
                  placeholder="모델이 읽을 자료를 넣어요"
                  aria-invalid={!!errors.text}
                  aria-describedby="sim-text-count sim-text-error"
                  className={`${controlClass} resize-y`}
                />
                <CharacterCount id="sim-text-count" value={text} />
                <FieldError
                  id="sim-text-error"
                  message={errors.text?.message}
                />
              </div>
            )}
            {isOpen("images") && (
              <div>
                <p className="mb-2 text-label font-semibold">이미지</p>
                <div className="flex flex-col gap-2.5 rounded-control border border-dashed border-grey-300 bg-grey-50 p-3.5">
                  {existingAssetIds.length > 0 && (
                    <ul
                      aria-label="재실행에 쓰는 기존 이미지"
                      className="space-y-1 text-body-sm"
                    >
                      {existingAssetIds.map((assetId, index) => {
                        const label = existingImageLabel(
                          assetId,
                          index,
                          existingImageNames,
                        );
                        return (
                          <li
                            key={assetId}
                            className="flex items-center justify-between gap-2 rounded-lg border border-grey-200 bg-white px-3 py-2"
                          >
                            <span className="min-w-0 break-all">{label}</span>
                            <button
                              type="button"
                              aria-label={`${label} 제거`}
                              onClick={() => removeExisting(index)}
                              className="shrink-0 rounded-lg px-2 text-grey-600 focus-visible:outline-2 focus-visible:outline-brand"
                            >
                              제거
                            </button>
                          </li>
                        );
                      })}
                    </ul>
                  )}
                  {files.length > 0 && (
                    <ul className="space-y-1 text-body-sm">
                      {files.map((file, index) => (
                        <li
                          key={fileKey(file)}
                          className="flex items-center justify-between gap-2 rounded-lg border border-grey-200 bg-white px-3 py-2"
                        >
                          <span className="min-w-0 break-all">{file.name}</span>
                          <button
                            type="button"
                            aria-label={`${file.name} 제거`}
                            onClick={() => removeFile(index)}
                            className="shrink-0 rounded-lg px-2 text-grey-600 focus-visible:outline-2 focus-visible:outline-brand"
                          >
                            제거
                          </button>
                        </li>
                      ))}
                    </ul>
                  )}
                  <div className="flex flex-wrap items-center gap-2.5">
                    <label
                      htmlFor="sim-files"
                      className="inline-flex h-8 cursor-pointer items-center rounded-lg bg-grey-100 px-2.5 text-label font-semibold text-grey-700 hover:bg-grey-200 has-focus-visible:outline-2 has-focus-visible:outline-offset-2 has-focus-visible:outline-brand"
                    >
                      파일 추가
                      <input
                        id="sim-files"
                        type="file"
                        accept={imageLimits.mimeTypes.join(",")}
                        multiple
                        aria-label="이미지 파일 추가"
                        aria-invalid={!!fileError}
                        aria-describedby="sim-files-help sim-files-error"
                        onChange={(event) => {
                          selectFiles(Array.from(event.target.files ?? []));
                          event.target.value = "";
                        }}
                        className="sr-only"
                      />
                    </label>
                    <p
                      id="sim-files-help"
                      className="text-caption text-grey-600"
                    >
                      JPG·PNG·WebP · 최대 {imageLimits.maxCount}개 · 파일당{" "}
                      {imageLimits.maxBytes / 1024 / 1024}MiB
                    </p>
                  </div>
                </div>
                <FieldError id="sim-files-error" message={fileError} />
              </div>
            )}
            {isOpen("schema") && (
              <div className="col-span-2">
                <label
                  htmlFor="sim-schema"
                  className="mb-2 block text-label font-semibold"
                >
                  JSON Schema
                </label>
                <textarea
                  {...register("jsonSchema")}
                  id="sim-schema"
                  rows={4}
                  spellCheck={false}
                  placeholder="출력 형식을 검증할 Schema를 JSON 객체로 적어요"
                  aria-invalid={!!errors.jsonSchema}
                  aria-describedby="sim-schema-error"
                  className={`${controlClass} resize-y font-mono`}
                />
                <FieldError
                  id="sim-schema-error"
                  message={errors.jsonSchema?.message}
                />
              </div>
            )}
          </div>
        )}
      </div>
      <OutputTypeField />
    </section>
  );
}

function CharacterCount({ id, value }: { id: string; value: string }) {
  const length = Array.from(value).length;
  return (
    <p
      id={id}
      className={`mt-1 text-right text-caption tabular-nums ${length > TEXT_LIMIT ? "text-red-600" : "text-grey-600"}`}
    >
      {formatCount(length)} / {formatCount(TEXT_LIMIT)}자
    </p>
  );
}
export function FieldError({ id, message }: { id: string; message?: string }) {
  return (
    <p
      id={id}
      role={message ? "alert" : undefined}
      className="mt-1 text-caption text-red-600"
    >
      {message}
    </p>
  );
}
