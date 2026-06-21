import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import type { Dataset } from "../api/datasets";
import { TransformationStudio } from "./TransformationStudio";

const dataset: Dataset = {
  id: "45d7c923-3c11-4ac7-8be7-08e6dc01c862",
  original_name: "customers.csv",
  file_format: "csv",
  size_bytes: 128,
  sha256: "0".repeat(64),
  sheet_name: "",
  row_count: 2,
  columns: [
    { name: "email", type: "text", missing_count: 0 },
    { name: "notes", type: "text", missing_count: 0 }
  ],
  text_columns: ["email", "notes"],
  preview: [{ email: "ada@example.com", notes: "Contact Ada" }],
  status: "ready",
  expires_at: "2026-06-21T10:00:00Z",
  created_at: "2026-06-21T09:00:00Z"
};

const proposal = {
  pattern: String.raw`\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b`,
  flags: [],
  explanation: "Matches email addresses.",
  assumptions: ["Addresses use a conventional domain."],
  positive_examples: ["ada@example.com"],
  negative_examples: ["ada at example dot com"],
  confidence: 0.98,
  provider: "built-in",
  model: "common-patterns-v1",
  data_rows_sent: 0
};

const preview = {
  pattern: proposal.pattern,
  replacement: "[REDACTED]",
  columns: ["email"],
  flags: [],
  match_count: 1,
  affected_rows: 1,
  changed_cells: 1,
  total_rows: 2,
  warnings: [],
  preview: [
    {
      row_index: 0,
      changes: [
        {
          column: "email",
          before: "ada@example.com",
          after: "[REDACTED]",
          matches: [{ start: 0, end: 15, text: "ada@example.com" }]
        }
      ]
    }
  ]
};

const run = {
  id: "44ca057f-2e60-4fb7-af65-d5e03f327bc3",
  dataset_id: dataset.id,
  transform_type: "regex_replace",
  parameters: {},
  instruction: "Find email addresses",
  pattern: proposal.pattern,
  flags: [],
  replacement: "[REDACTED]",
  columns: ["email"],
  explanation: proposal.explanation,
  provider: proposal.provider,
  model_name: proposal.model,
  status: "completed",
  match_count: 1,
  affected_rows: 1,
  changed_cells: 1,
  warnings: [],
  result_columns: ["email", "notes"],
  result_preview: [{ email: "[REDACTED]", notes: "Contact Ada" }],
  output_format: "csv",
  download_url: "/api/transforms/44ca057f-2e60-4fb7-af65-d5e03f327bc3/download/",
  created_at: "2026-06-21T09:05:00Z"
};

function jsonResponse(payload: unknown, status = 200) {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "Content-Type": "application/json" }
  });
}

describe("TransformationStudio", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("drives a proposal through preview, approval, and download", async () => {
    const user = userEvent.setup();
    const fetchMock = vi
      .fn<typeof fetch>()
      .mockResolvedValueOnce(jsonResponse(proposal))
      .mockResolvedValueOnce(jsonResponse(preview))
      .mockResolvedValueOnce(jsonResponse(run, 201));
    vi.stubGlobal("fetch", fetchMock);
    const onComplete = vi.fn();
    const onPreview = vi.fn();
    const onPreviewInvalidated = vi.fn();
    const queryClient = new QueryClient({
      defaultOptions: { mutations: { retry: false }, queries: { retry: false } }
    });

    render(
      <QueryClientProvider client={queryClient}>
        <TransformationStudio
          dataset={dataset}
          onComplete={onComplete}
          onPreview={onPreview}
          onPreviewInvalidated={onPreviewInvalidated}
        />
      </QueryClientProvider>
    );

    await user.type(
      screen.getByLabelText("2. Describe what to match"),
      "Find email addresses"
    );
    await user.click(screen.getByRole("button", { name: "Generate regex proposal" }));

    expect(await screen.findByDisplayValue(proposal.pattern)).toBeInTheDocument();
    expect(screen.getByText(/No dataset rows included by this app/)).toBeInTheDocument();
    expect(screen.getByText("Preview required")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Preview changes" }));

    expect(await screen.findByText("Trust gate passed")).toBeInTheDocument();
    const previewResults = screen
      .getByRole("heading", { name: "Review every proposed change" })
      .closest("section")!;
    expect(within(previewResults).getByText("ada@example.com")).toBeInTheDocument();
    expect(within(previewResults).getByText("[REDACTED]")).toBeInTheDocument();
    expect(onPreview).toHaveBeenCalledOnce();

    await user.click(screen.getByRole("button", { name: "Approve and apply" }));

    const download = await screen.findByRole("link", { name: "Download CSV" });
    expect(download).toHaveAttribute("href", run.download_url);
    expect(screen.getByRole("heading", { name: "Applied replacement results" }))
      .toBeInTheDocument();
    expect(onComplete).toHaveBeenCalledOnce();
    expect(fetchMock).toHaveBeenCalledTimes(3);

    expect(JSON.parse(String(fetchMock.mock.calls[0][1]?.body))).toEqual({
      instruction: "Find email addresses",
      columns: ["email"]
    });
    expect(JSON.parse(String(fetchMock.mock.calls[1][1]?.body))).toEqual({
      pattern: proposal.pattern,
      replacement: "[REDACTED]",
      columns: ["email"],
      flags: []
    });
    expect(JSON.parse(String(fetchMock.mock.calls[2][1]?.body))).toEqual(
      expect.objectContaining({
        instruction: "Find email addresses",
        pattern: proposal.pattern,
        provider: "built-in",
        model: "common-patterns-v1"
      })
    );
  });
});
