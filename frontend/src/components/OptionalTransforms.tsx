import { useState } from "react";
import { useMutation } from "@tanstack/react-query";

import type { Dataset } from "../api/datasets";
import { ProcessedOutput } from "./ProcessedOutput";
import {
  applyAiTransform,
  generateAiTransformPlan,
  previewAiTransform,
  type AiTransformOperation,
  type AiTransformPlan,
  type AiTransformPreview
} from "../api/transformations";

type OptionalTransformsProps = {
  dataset: Dataset;
  onComplete: () => void;
  onPreview: () => void;
  onPreviewInvalidated: () => void;
};

const operations: {
  value: AiTransformOperation;
  title: string;
  description: string;
  placeholder: string;
}[] = [
  {
    value: "standardize_categories",
    title: "Standardize categories",
    description: "Map known variants to a reviewable canonical vocabulary.",
    placeholder: "Standardize Australian state names to abbreviations"
  },
  {
    value: "extract_fields",
    title: "Extract fields",
    description: "Add structured columns using named, inspectable capture groups.",
    placeholder: "Split full names into first_name and last_name"
  }
];

function preferredColumn(dataset: Dataset, operation: AiTransformOperation) {
  const preferredTerms =
    operation === "standardize_categories" ? ["state", "territory"] : ["name"];
  const lowerByColumn = new Map(
    dataset.text_columns.map((columnName) => [columnName, columnName.toLowerCase()])
  );
  return (
    dataset.text_columns.find((columnName) =>
      preferredTerms.includes(lowerByColumn.get(columnName) ?? "")
    ) ??
    dataset.text_columns.find((columnName) =>
      preferredTerms.some((term) => lowerByColumn.get(columnName)?.includes(term))
    ) ??
    dataset.text_columns[0] ??
    ""
  );
}

export function OptionalTransforms({
  dataset,
  onComplete,
  onPreview,
  onPreviewInvalidated
}: OptionalTransformsProps) {
  const [operation, setOperation] = useState<AiTransformOperation>("standardize_categories");
  const [column, setColumn] = useState(preferredColumn(dataset, "standardize_categories"));
  const [instruction, setInstruction] = useState("");
  const [parametersText, setParametersText] = useState("");
  const [plan, setPlan] = useState<AiTransformPlan>();
  const [parameterError, setParameterError] = useState<string>();

  const apply = useMutation({ mutationFn: applyAiTransform, onSuccess: onComplete });
  const preview = useMutation({ mutationFn: previewAiTransform, onSuccess: onPreview });
  const generation = useMutation({
    mutationFn: generateAiTransformPlan,
    onSuccess: (result) => {
      setPlan(result);
      setParametersText(JSON.stringify(result.parameters, null, 2));
      setParameterError(undefined);
      preview.reset();
      apply.reset();
      onPreviewInvalidated();
    }
  });

  const invalidate = () => {
    setPlan(undefined);
    setParametersText("");
    setParameterError(undefined);
    preview.reset();
    apply.reset();
    onPreviewInvalidated();
  };

  const parseParameters = () => {
    try {
      const value: unknown = JSON.parse(parametersText);
      if (!value || typeof value !== "object" || Array.isArray(value)) {
        throw new Error("Plan parameters must be a JSON object.");
      }
      setParameterError(undefined);
      return value as Record<string, unknown>;
    } catch (error) {
      setParameterError(error instanceof Error ? error.message : "Plan parameters are invalid.");
      return undefined;
    }
  };

  const requestPreview = () => {
    const parameters = parseParameters();
    if (parameters) {
      preview.mutate({ datasetId: dataset.id, operation, column, parameters });
    }
  };

  const requestApply = () => {
    const parameters = parseParameters();
    if (parameters) {
      apply.mutate({
        datasetId: dataset.id,
        operation,
        column,
        parameters,
        instruction,
        explanation: plan?.explanation,
        provider: plan?.provider,
        model: plan?.model
      });
    }
  };

  const selectedOperation = operations.find((item) => item.value === operation)!;

  return (
    <section className="optional-transforms" aria-labelledby="optional-heading">
      <header className="optional-heading">
        <div>
          <p className="eyebrow">Optional AI workflows</p>
          <h2 id="optional-heading">Two more transformations, same trust contract</h2>
          <p>AI proposes deterministic parameters. Values remain local and every result is previewed.</p>
        </div>
        <span>0 data rows sent to AI</span>
      </header>

      <div className="operation-picker">
        {operations.map((item) => (
          <button
            type="button"
            aria-pressed={operation === item.value}
            className={operation === item.value ? "selected" : ""}
            disabled={generation.isPending}
            key={item.value}
            onClick={() => {
              setOperation(item.value);
              setColumn(preferredColumn(dataset, item.value));
              setInstruction("");
              invalidate();
            }}
          >
            <strong>{item.title}</strong>
            <span>{item.description}</span>
          </button>
        ))}
      </div>

      <div className="optional-grid">
        <div className="optional-form">
          <label className="field-label" htmlFor="optional-column">
            <span>Source column</span>
            <select
              id="optional-column"
              value={column}
              disabled={generation.isPending}
              onChange={(event) => {
                setColumn(event.target.value);
                invalidate();
              }}
            >
              {dataset.text_columns.map((name) => <option key={name}>{name}</option>)}
            </select>
          </label>

          <label className="field-label" htmlFor="optional-instruction">
            <span>Transformation request</span>
            <textarea
              id="optional-instruction"
              value={instruction}
              rows={3}
              maxLength={1000}
              placeholder={selectedOperation.placeholder}
              disabled={generation.isPending}
              onChange={(event) => {
                setInstruction(event.target.value);
                invalidate();
              }}
            />
          </label>

          <button
            className="primary-button"
            type="button"
            disabled={!column || !instruction.trim() || generation.isPending}
            onClick={() =>
              generation.mutate({ datasetId: dataset.id, operation, instruction, column })
            }
          >
            {generation.isPending ? "Generating plan..." : "Generate transformation plan"}
          </button>
          {generation.error ? <InlineError message={generation.error.message} /> : null}

          {parametersText ? (
            <>
              <label className="field-label" htmlFor="optional-parameters">
                <span>Inspect or edit deterministic parameters</span>
                <textarea
                  id="optional-parameters"
                  className="code-area"
                  value={parametersText}
                  rows={10}
                  spellCheck={false}
                  onChange={(event) => {
                    setParametersText(event.target.value);
                    setPlan(undefined);
                    preview.reset();
                    apply.reset();
                    onPreviewInvalidated();
                  }}
                />
              </label>
              <button className="preview-button" type="button" onClick={requestPreview}>
                {preview.isPending ? "Previewing..." : "Preview optional transform"}
              </button>
            </>
          ) : null}
          {parameterError ? <InlineError message={parameterError} /> : null}
          {preview.error ? <InlineError message={preview.error.message} /> : null}
        </div>

        <aside className="optional-inspector">
          {plan ? <PlanSummary plan={plan} /> : <PlanEmpty operation={selectedOperation.title} />}
        </aside>
      </div>

      {preview.data ? (
        <OptionalPreview
          applyError={apply.error?.message}
          isApplying={apply.isPending}
          onApply={requestApply}
          preview={preview.data}
          run={apply.data}
        />
      ) : null}
    </section>
  );
}

function PlanSummary({ plan }: { plan: AiTransformPlan }) {
  return (
    <div className="plan-summary">
      <div className="proposal-meta">
        <span>{plan.provider}</span>
        <span>{plan.model}</span>
        <strong>{Math.round(plan.confidence * 100)}% model estimate</strong>
      </div>
      <h3>Model interpretation</h3>
      <p>{plan.explanation}</p>
      <dl>
        <div><dt>Operation</dt><dd>{plan.operation.replaceAll("_", " ")}</dd></div>
        <div><dt>Column</dt><dd>{plan.column}</dd></div>
      </dl>
      <p className="data-boundary">
        No dataset rows included by this app. The instruction and selected column name are sent.
      </p>
    </div>
  );
}

function PlanEmpty({ operation }: { operation: string }) {
  return (
    <div className="proposal-empty">
      <span aria-hidden="true">AI</span>
      <h3>{operation}</h3>
      <p>Generate a plan to inspect its deterministic mapping or named extraction groups.</p>
    </div>
  );
}

function OptionalPreview({
  applyError,
  isApplying,
  onApply,
  preview,
  run
}: {
  applyError?: string;
  isApplying: boolean;
  onApply: () => void;
  preview: AiTransformPreview;
  run?: Awaited<ReturnType<typeof applyAiTransform>>;
}) {
  if (run) {
    return (
      <div className="completed-output" role="status">
        <div className="run-receipt">
          <div>
            <p className="eyebrow">Optional transform complete</p>
            <h3>{run.transform_type.replaceAll("_", " ")}</h3>
            <p>{run.affected_rows} rows changed. The original dataset remains untouched.</p>
            {run.warnings.map((warning) => <small key={warning}>{warning}</small>)}
          </div>
          <a className="download-button" href={run.download_url}>
            Download {run.output_format.toUpperCase()}
          </a>
        </div>
        <ProcessedOutput columns={run.result_columns} rows={run.result_preview} />
      </div>
    );
  }

  return (
    <div className="optional-preview">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Preview</p>
          <h3>{preview.affected_rows} rows will change</h3>
        </div>
        <span>Outputs: {preview.output_columns.join(", ")}</span>
      </div>
      <div className="optional-preview-list">
        {preview.preview.map((row, index) => (
          <pre key={String(row.row_index ?? index)}>{JSON.stringify(row, null, 2)}</pre>
        ))}
      </div>
      {preview.warnings.map((warning) => <p className="warning-panel" key={warning}>{warning}</p>)}
      {applyError ? <InlineError message={applyError} /> : null}
      <button className="apply-optional-button" type="button" disabled={isApplying} onClick={onApply}>
        {isApplying ? "Applying..." : "Approve and apply optional transform"}
      </button>
    </div>
  );
}

function InlineError({ message }: { message: string }) {
  return <p className="inline-error compact" role="alert">{message}</p>;
}
