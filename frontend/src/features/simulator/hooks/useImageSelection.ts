import { useFormContext } from "react-hook-form";
import type { SimulatorDraft, SimulatorFormValues } from "../lib/form";
import { fileKey, imageFilesSchema } from "../lib/images";

export function useImageSelection() {
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
    const result = imageFilesSchema.safeParse(merged);
    if (!result.success) {
      setError("files", {
        type: "imageSelection",
        message: result.error.issues[0].message,
      });
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
  return { selectFiles, removeFile };
}
