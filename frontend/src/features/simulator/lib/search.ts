import { z } from "zod";
import { SORT_KEYS } from "./presentation";

export const simulatorSearchSchema = z.object({
  sort: z.enum(SORT_KEYS).catch("model"),
  direction: z.enum(["asc", "desc"]).catch("asc"),
  sourceRun: z.string().trim().min(1).max(128).optional().catch(undefined),
});
