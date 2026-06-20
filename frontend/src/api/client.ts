import { z } from "zod";

const errorSchema = z.object({
  code: z.string(),
  message: z.string()
});

export class ApiError extends Error {
  constructor(
    message: string,
    readonly code = "request_failed"
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export async function requestJson<T>(
  url: string,
  init: RequestInit,
  schema: z.ZodType<T>
): Promise<T> {
  const response = await fetch(url, init);
  const payload: unknown = await response.json().catch(() => null);

  if (!response.ok) {
    const parsedError = errorSchema.safeParse(payload);
    throw new ApiError(
      parsedError.success ? parsedError.data.message : "The request could not be completed.",
      parsedError.success ? parsedError.data.code : undefined
    );
  }

  const parsedPayload = schema.safeParse(payload);
  if (!parsedPayload.success) {
    throw new ApiError("The server returned an unexpected response.");
  }
  return parsedPayload.data;
}
