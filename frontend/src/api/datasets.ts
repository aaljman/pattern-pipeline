import { z } from "zod";

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

const errorSchema = z.object({
  code: z.string(),
  message: z.string()
});

export type Dataset = z.infer<typeof datasetSchema>;
export type DatasetColumn = z.infer<typeof columnSchema>;

export class ApiError extends Error {
  constructor(
    message: string,
    readonly code = "request_failed"
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export async function uploadDataset(file: File): Promise<Dataset> {
  const body = new FormData();
  body.append("file", file);

  const response = await fetch("/api/datasets/", {
    method: "POST",
    body
  });
  const payload: unknown = await response.json().catch(() => null);

  if (!response.ok) {
    const parsedError = errorSchema.safeParse(payload);
    throw new ApiError(
      parsedError.success ? parsedError.data.message : "The upload could not be completed.",
      parsedError.success ? parsedError.data.code : undefined
    );
  }

  const parsedDataset = datasetSchema.safeParse(payload);
  if (!parsedDataset.success) {
    throw new ApiError("The server returned an unexpected dataset profile.");
  }
  return parsedDataset.data;
}
