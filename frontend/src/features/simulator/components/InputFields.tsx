import { useFormContext, useWatch } from "react-hook-form";
import { formatCount } from "../../../shared/lib/format";
import { useImageSelection } from "../hooks/useImageSelection";
import type { SimulatorDraft, SimulatorFormValues } from "../lib/form";
import { fileKey } from "../lib/images";
import { controlClass, type ImageLimits, TEXT_LIMIT } from "../lib/limits";
import type { ScenarioChoice } from "../lib/presentation";

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
  const [mode, prompt, text, files, existingAssetIds] = useWatch({
    control,
    name: ["mode", "prompt", "text", "files", "existingAssetIds"],
  });
  const fileError =
    errors.files?.message ??
    errors.files?.root?.message ??
    files.map((_, index) => errors.files?.[index]?.message).find(Boolean);
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
    <div className="grid grid-cols-2 gap-x-6 gap-y-5 pb-6">
      <div className="flex flex-col gap-5">
        <div>
          <label
            htmlFor="sim-mode"
            className="mb-2 block text-label font-semibold"
          >
            테스트 유형
          </label>
          <select {...register("mode")} id="sim-mode" className={controlClass}>
            <option value="custom">Custom Prompt</option>
            <option value="scenario" disabled={!scenarios.length}>
              기본 시나리오
            </option>
          </select>
        </div>
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
              <option value="">시나리오를 선택하시기 바랍니다</option>
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
          <label
            htmlFor="sim-text"
            className="mb-2 block text-label font-semibold"
          >
            입력 텍스트{" "}
            <span className="font-normal text-grey-600">(선택사항)</span>
          </label>
          <textarea
            {...register("text")}
            id="sim-text"
            rows={4}
            placeholder="분석할 텍스트를 입력하시기 바랍니다"
            aria-invalid={!!errors.text}
            aria-describedby="sim-text-count sim-text-error"
            className={`${controlClass} resize-y`}
          />
          <CharacterCount id="sim-text-count" value={text} />
          <FieldError id="sim-text-error" message={errors.text?.message} />
        </div>
      </div>
      <div>
        <label
          htmlFor="sim-prompt"
          className="mb-2 block text-label font-semibold"
        >
          Prompt
        </label>
        <textarea
          {...register("prompt")}
          id="sim-prompt"
          rows={9}
          placeholder="모델이 수행할 작업을 입력하시기 바랍니다"
          aria-invalid={!!errors.prompt}
          aria-describedby="sim-prompt-count sim-prompt-error"
          className={`${controlClass} resize-y`}
        />
        <CharacterCount id="sim-prompt-count" value={prompt} />
        <FieldError id="sim-prompt-error" message={errors.prompt?.message} />
      </div>
      <div>
        <label
          htmlFor="sim-files"
          className="mb-2 block text-label font-semibold"
        >
          이미지 <span className="font-normal text-grey-600">(선택사항)</span>
        </label>
        <input
          id="sim-files"
          type="file"
          accept={imageLimits.mimeTypes.join(",")}
          multiple
          aria-invalid={!!fileError}
          aria-describedby="sim-files-help sim-files-error"
          onChange={(event) => {
            selectFiles(Array.from(event.target.files ?? []));
            event.target.value = "";
          }}
          className={`${controlClass} file:mr-3 file:rounded-lg file:border-0 file:bg-grey-100 file:px-3 file:py-1 file:text-grey-700`}
        />
        <p id="sim-files-help" className="mt-2 text-caption text-grey-600">
          JPG·PNG·WebP · 최대 {imageLimits.maxCount}개 · 파일당{" "}
          {imageLimits.maxBytes / 1024 / 1024}MiB
        </p>
        {existingAssetIds.length > 0 && (
          <ul
            aria-label="재실행에 쓰는 기존 이미지"
            className="mt-2 space-y-1 text-body-sm"
          >
            {existingAssetIds.map((assetId, index) => (
              <li
                key={assetId}
                className="flex items-center justify-between gap-2 rounded-lg bg-grey-50 px-3 py-2"
              >
                <span>기존 이미지 {index + 1}</span>
                <button
                  type="button"
                  aria-label={`기존 이미지 ${index + 1} 제거`}
                  onClick={() => removeExisting(index)}
                  className="shrink-0 rounded-lg px-2 text-grey-600 focus-visible:outline-2 focus-visible:outline-brand"
                >
                  제거
                </button>
              </li>
            ))}
          </ul>
        )}
        {files.length > 0 && (
          <ul className="mt-2 space-y-1 text-body-sm">
            {files.map((file, index) => (
              <li
                key={fileKey(file)}
                className="flex items-center justify-between gap-2 rounded-lg bg-grey-50 px-3 py-2"
              >
                <span className="min-w-0 break-all">{file.name}</span>
                <button
                  type="button"
                  aria-label={`이미지 ${index + 1} 제거`}
                  onClick={() => removeFile(index)}
                  className="shrink-0 rounded-lg px-2 text-grey-600 focus-visible:outline-2 focus-visible:outline-brand"
                >
                  제거
                </button>
              </li>
            ))}
          </ul>
        )}
        <FieldError id="sim-files-error" message={fileError} />
      </div>
      <div>
        <label
          htmlFor="sim-schema"
          className="mb-2 block text-label font-semibold"
        >
          JSON Schema{" "}
          <span className="font-normal text-grey-600">(선택사항)</span>
        </label>
        <textarea
          {...register("jsonSchema")}
          id="sim-schema"
          rows={4}
          spellCheck={false}
          placeholder="출력 형식을 검증할 Schema를 입력하시기 바랍니다"
          aria-invalid={!!errors.jsonSchema}
          aria-describedby="sim-schema-error"
          className={`${controlClass} resize-y font-mono`}
        />
        <FieldError
          id="sim-schema-error"
          message={errors.jsonSchema?.message}
        />
      </div>
    </div>
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
