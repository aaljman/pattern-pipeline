import { z } from "zod";

import { requestJson } from "./client";

const columnSchema = z.object({
  name: z.string(),
  type: z.enum(["text", "number", "boolean", "datetime"]),
  missing_count: z.number().int().nonnegative()
});

const datasetSchema = z.object({
  id: z.string().uuid(),
  original_name: z.string(),
  file_format: z.enum(["csv", "xlsx"]),
  size_bytes: z.number().nonnegative(),
  sha256: z.string(),
  sheet_name: z.string(),
  row_count: z.number().int().nonnegative(),
  columns: z.array(columnSchema),
  text_columns: z.array(z.string()),
  preview: z.array(z.record(z.string(), z.unknown())),
  status: z.enum(["ready", "failed"]),
  expires_at: z.string(),
  created_at: z.string()
});

export type Dataset = z.infer<typeof datasetSchema>;
export type DatasetColumn = z.infer<typeof columnSchema>;

export async function uploadDataset(file: File): Promise<Dataset> {
  const body = new FormData();
  body.append("file", file);

  return requestJson("/api/datasets/", { method: "POST", body }, datasetSchema);
}
