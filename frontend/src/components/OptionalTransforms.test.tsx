import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import type { Dataset } from "../api/datasets";
import { OptionalTransforms } from "./OptionalTransforms";

const dataset: Dataset = {
  id: "d8cfb31e-128c-4627-840f-ed642e23f91f",
  original_name: "customers.csv",
  file_format: "csv",
  size_bytes: 96,
  sha256: "1".repeat(64),
  sheet_name: "",
  row_count: 2,
  columns: [{ name: "state", type: "text", missing_count: 0 }],
  text_columns: ["state"],
  preview: [{ state: "New South Wales" }, { state: "NSW" }],
  status: "ready",
  expires_at: "2026-06-21T10:00:00Z",
  created_at: "2026-06-21T09:00:00Z"
};

const mixedColumnsDataset: Dataset = {
  ...dataset,
  columns: [
    { name: "customer_id", type: "text", missing_count: 0 },
    { name: "name", type: "text", missing_count: 0 },
    { name: "state", type: "text", missing_count: 0 },
    { name: "email", type: "text", missing_count: 0 }
  ],
  text_columns: ["customer_id", "name", "state", "email"],
  preview: [
    {
      customer_id: "C-001",
      name: "Ada Lovelace",
      state: "New South Wales",
      email: "ada@example.com"
    }
  ]
};

const plan = {
  operation: "standardize_categories",
  column: "state",
  parameters: { mapping: { "New South Wales": "NSW" } },
  explanation: "Maps a full state name to its canonical abbreviation.",
  confidence: 0.99,
  provider: "built-in",
  model: "category-standardizer-v1",
  data_rows_sent: 0
};

const preview = {
  operation: "standardize_categories",
  column: "state",
  affected_rows: 1,
  changed_cells: 1,
  total_rows: 2,
  output_columns: ["state"],
  warnings: [],
  preview: [{ row_index: 0, before: "New South Wales", after: "NSW" }]
};

const run = {
  id: "72fc9ac8-e671-432c-bd1d-ac83d6771c59",
  dataset_id: dataset.id,
  transform_type: "standardize_categories",
  parameters: plan.parameters,
  instruction: "Standardize Australian state names",
  pattern: "",
  flags: [],
  replacement: "",
  columns: ["state"],
  explanation: plan.explanation,
  provider: plan.provider,
  model_name: plan.model,
  status: "completed",
  match_count: 0,
  affected_rows: 1,
  changed_cells: 1,
  warnings: [],
  result_columns: ["state"],
  result_preview: [{ state: "NSW" }, { state: "NSW" }],
  output_format: "csv",
  download_url: "/api/transforms/72fc9ac8-e671-432c-bd1d-ac83d6771c59/download/",
  created_at: "2026-06-21T09:05:00Z"
};

function jsonResponse(payload: unknown, status = 200) {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "Content-Type": "application/json" }
  });
}

describe("OptionalTransforms", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("chooses workflow-friendly source column defaults", async () => {
    const user = userEvent.setup();
    const queryClient = new QueryClient({
      defaultOptions: { mutations: { retry: false }, queries: { retry: false } }
    });

    render(
      <QueryClientProvider client={queryClient}>
        <OptionalTransforms
          dataset={mixedColumnsDataset}
          onComplete={vi.fn()}
          onPreview={vi.fn()}
          onPreviewInvalidated={vi.fn()}
        />
      </QueryClientProvider>
    );

    expect(screen.getByLabelText("Source column")).toHaveValue("state");

    await user.click(screen.getByRole("button", { name: /Extract fields/ }));

    expect(screen.getByLabelText("Source column")).toHaveValue("name");
  });

  it("previews and applies a deterministic category plan", async () => {
    const user = userEvent.setup();
    const fetchMock = vi
      .fn<typeof fetch>()
      .mockResolvedValueOnce(jsonResponse(plan))
      .mockResolvedValueOnce(jsonResponse(preview))
      .mockResolvedValueOnce(jsonResponse(run, 201));
    vi.stubGlobal("fetch", fetchMock);
    const onComplete = vi.fn();
    const onPreview = vi.fn();
    const queryClient = new QueryClient({
      defaultOptions: { mutations: { retry: false }, queries: { retry: false } }
    });

    render(
      <QueryClientProvider client={queryClient}>
        <OptionalTransforms
          dataset={dataset}
          onComplete={onComplete}
          onPreview={onPreview}
          onPreviewInvalidated={vi.fn()}
        />
      </QueryClientProvider>
    );

    await user.type(
      screen.getByLabelText("Transformation request"),
      "Standardize Australian state names"
    );
    await user.click(screen.getByRole("button", { name: "Generate transformation plan" }));

    const parameters = await screen.findByLabelText(
      "Inspect or edit deterministic parameters"
    );
    expect(parameters).toHaveValue(JSON.stringify(plan.parameters, null, 2));
    expect(screen.getByText(/No dataset rows included by this app/)).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Preview optional transform" }));

    expect(await screen.findByRole("heading", { name: "1 rows will change" }))
      .toBeInTheDocument();
    expect(screen.getByText(/New South Wales/, { selector: "pre" })).toBeInTheDocument();
    expect(onPreview).toHaveBeenCalledOnce();

    await user.click(
      screen.getByRole("button", { name: "Approve and apply optional transform" })
    );

    const download = await screen.findByRole("link", { name: "Download CSV" });
    expect(download).toHaveAttribute("href", run.download_url);
    expect(onComplete).toHaveBeenCalledOnce();
    expect(fetchMock).toHaveBeenCalledTimes(3);
    expect(JSON.parse(String(fetchMock.mock.calls[2][1]?.body))).toEqual(
      expect.objectContaining({
        operation: "standardize_categories",
        column: "state",
        parameters: plan.parameters,
        provider: "built-in"
      })
    );
  });
});
