import { useFormContext } from "react-hook-form";
import type { SimulatorDraft, SimulatorFormValues } from "../lib/form";
import { fileKey, imageCountMessage, imageFilesSchemaFor } from "../lib/images";
import type { ImageLimits } from "../lib/limits";

export function useImageSelection(limits: ImageLimits) {
  const { getValues, setValue, setError, clearErrors } = useFormContext<
    SimulatorFormValues,
    unknown,
    SimulatorDraft
  >();
  const selectFiles = (incoming: File[]) => {
    if (!incoming.length) return;
    const merged = [
      ...new Map(
        [...getValues("files"), ...incoming].map((file) => [
          fileKey(file),
          file,
        ]),
      ).values(),
    ];
    const result = imageFilesSchemaFor(limits).safeParse(merged);
    const total = merged.length + getValues("existingAssetIds").length;
    const message = !result.success
      ? result.error.issues[0].message
      : total > limits.maxCount
        ? imageCountMessage(limits)
        : undefined;
    if (message || !result.success) {
      setError("files", { type: "imageSelection", message });
      return;
    }
    setValue("files", result.data, { shouldDirty: true });
    clearErrors("files");
  };
  const removeFile = (index: number) => {
    setValue(
      "files",
      getValues("files").filter((_, i) => i !== index),
      { shouldDirty: true },
    );
    clearErrors("files");
  };
  const removeExisting = (index: number) => {
    setValue(
      "existingAssetIds",
      getValues("existingAssetIds").filter((_, i) => i !== index),
      { shouldDirty: true },
    );
    clearErrors("files");
  };
  return { selectFiles, removeFile, removeExisting };
}
