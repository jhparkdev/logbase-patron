import { z } from "zod";
import { SORT_KEYS } from "./presentation";

export const simulatorSearchSchema = z.object({
  sort: z.enum(SORT_KEYS).catch("model"),
  direction: z.enum(["asc", "desc"]).catch("asc"),
  // 서버가 UUID만 받으므로 다른 값은 지운다
  sourceRun: z.guid().optional().catch(undefined),
  run: z.guid().optional().catch(undefined),
});
