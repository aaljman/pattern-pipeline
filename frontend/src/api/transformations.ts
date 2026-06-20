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

export type RegexFlag = z.infer<typeof regexFlagSchema>;
export type RegexProposal = z.infer<typeof regexProposalSchema>;
export type TransformationPreview = z.infer<typeof previewSchema>;
export type MatchSpan = z.infer<typeof matchSchema>;

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
