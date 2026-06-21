import { z } from "zod";

import { requestJson } from "./client";

export const regexFlagSchema = z.enum(["IGNORECASE", "MULTILINE"]);

const regexProposalSchema = z.object({
  pattern: z.string(),
  flags: z.array(regexFlagSchema),
  explanation: z.string(),
  assumptions: z.array(z.string()),
  positive_examples: z.array(z.string()),
  negative_examples: z.array(z.string()),
  confidence: z.number().min(0).max(1),
  provider: z.string(),
  model: z.string(),
  data_rows_sent: z.literal(0)
});

const matchSchema = z.object({
  start: z.number().int().nonnegative(),
  end: z.number().int().nonnegative(),
  text: z.string()
});

const previewSchema = z.object({
  pattern: z.string(),
  replacement: z.string(),
  columns: z.array(z.string()),
  flags: z.array(regexFlagSchema),
  match_count: z.number().int().nonnegative(),
  affected_rows: z.number().int().nonnegative(),
  changed_cells: z.number().int().nonnegative(),
  total_rows: z.number().int().nonnegative(),
  warnings: z.array(z.string()),
  preview: z.array(
    z.object({
      row_index: z.number().int().nonnegative(),
      changes: z.array(
        z.object({
          column: z.string(),
          before: z.string(),
          after: z.string(),
          matches: z.array(matchSchema)
        })
      )
    })
  )
});

export const transformRunSchema = z.object({
  id: z.string().uuid(),
  dataset_id: z.string().uuid(),
  transform_type: z.enum([
    "regex_replace",
    "standardize_categories",
    "extract_fields"
  ]),
  parameters: z.record(z.string(), z.unknown()),
  instruction: z.string(),
  pattern: z.string(),
  flags: z.array(regexFlagSchema),
  replacement: z.string(),
  columns: z.array(z.string()),
  explanation: z.string(),
  provider: z.string(),
  model_name: z.string(),
  status: z.enum(["completed", "failed"]),
  match_count: z.number().int().nonnegative(),
  affected_rows: z.number().int().nonnegative(),
  changed_cells: z.number().int().nonnegative(),
  warnings: z.array(z.string()),
  result_columns: z.array(z.string()),
  result_preview: z.array(z.record(z.string(), z.unknown())),
  output_format: z.enum(["csv", "xlsx"]),
  download_url: z.string(),
  created_at: z.string()
});

export const aiTransformOperationSchema = z.enum([
  "standardize_categories",
  "extract_fields"
]);

const aiTransformPlanSchema = z.object({
  operation: aiTransformOperationSchema,
  column: z.string(),
  parameters: z.record(z.string(), z.unknown()),
  explanation: z.string(),
  confidence: z.number().min(0).max(1),
  provider: z.string(),
  model: z.string(),
  data_rows_sent: z.literal(0)
});

const aiTransformPreviewSchema = z.object({
  operation: aiTransformOperationSchema,
  column: z.string(),
  affected_rows: z.number().int().nonnegative(),
  changed_cells: z.number().int().nonnegative(),
  total_rows: z.number().int().nonnegative(),
  output_columns: z.array(z.string()),
  warnings: z.array(z.string()),
  preview: z.array(z.record(z.string(), z.unknown()))
});

export type RegexFlag = z.infer<typeof regexFlagSchema>;
export type RegexProposal = z.infer<typeof regexProposalSchema>;
export type TransformationPreview = z.infer<typeof previewSchema>;
export type MatchSpan = z.infer<typeof matchSchema>;
export type TransformRun = z.infer<typeof transformRunSchema>;
export type AiTransformOperation = z.infer<typeof aiTransformOperationSchema>;
export type AiTransformPlan = z.infer<typeof aiTransformPlanSchema>;
export type AiTransformPreview = z.infer<typeof aiTransformPreviewSchema>;

type GenerateRegexInput = {
  datasetId: string;
  instruction: string;
  columns: string[];
};

type PreviewTransformationInput = {
  datasetId: string;
  pattern: string;
  replacement: string;
  columns: string[];
  flags: RegexFlag[];
};

export type ApplyTransformationInput = PreviewTransformationInput & {
  instruction: string;
  explanation?: string;
  provider?: string;
  model?: string;
};

export function generateRegex(input: GenerateRegexInput) {
  return requestJson(
    `/api/datasets/${input.datasetId}/transforms/generate/`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ instruction: input.instruction, columns: input.columns })
    },
    regexProposalSchema
  );
}

export function previewTransformation(input: PreviewTransformationInput) {
  return requestJson(
    `/api/datasets/${input.datasetId}/transforms/preview/`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        pattern: input.pattern,
        replacement: input.replacement,
        columns: input.columns,
        flags: input.flags
      })
    },
    previewSchema
  );
}

export function applyTransformation(input: ApplyTransformationInput) {
  return requestJson(
    `/api/datasets/${input.datasetId}/transforms/apply/`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        pattern: input.pattern,
        replacement: input.replacement,
        columns: input.columns,
        flags: input.flags,
        instruction: input.instruction,
        explanation: input.explanation ?? "",
        provider: input.provider ?? "",
        model: input.model ?? ""
      })
    },
    transformRunSchema
  );
}

type GenerateAiTransformInput = {
  datasetId: string;
  operation: AiTransformOperation;
  instruction: string;
  column: string;
};

type AiTransformExecutionInput = {
  datasetId: string;
  operation: AiTransformOperation;
  column: string;
  parameters: Record<string, unknown>;
};

export function generateAiTransformPlan(input: GenerateAiTransformInput) {
  return requestJson(
    `/api/datasets/${input.datasetId}/ai-transforms/generate/`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        operation: input.operation,
        instruction: input.instruction,
        column: input.column
      })
    },
    aiTransformPlanSchema
  );
}

export function previewAiTransform(input: AiTransformExecutionInput) {
  return requestJson(
    `/api/datasets/${input.datasetId}/ai-transforms/preview/`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        operation: input.operation,
        column: input.column,
        parameters: input.parameters
      })
    },
    aiTransformPreviewSchema
  );
}

export function applyAiTransform(
  input: AiTransformExecutionInput & {
    instruction: string;
    explanation?: string;
    provider?: string;
    model?: string;
  }
) {
  return requestJson(
    `/api/datasets/${input.datasetId}/ai-transforms/apply/`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        operation: input.operation,
        column: input.column,
        parameters: input.parameters,
        instruction: input.instruction,
        explanation: input.explanation ?? "",
        provider: input.provider ?? "",
        model: input.model ?? ""
      })
    },
    transformRunSchema
  );
}
