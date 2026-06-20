import { useState } from "react";
import { useMutation } from "@tanstack/react-query";

import type { Dataset } from "../api/datasets";
import {
  generateRegex,
  previewTransformation,
  type MatchSpan,
  type RegexFlag,
  type RegexProposal
} from "../api/transformations";

type TransformationStudioProps = {
  dataset: Dataset;
};

const supportedFlags: { label: string; value: RegexFlag }[] = [
  { label: "Ignore case", value: "IGNORECASE" },
  { label: "Multiline", value: "MULTILINE" }
];

export function TransformationStudio({ dataset }: TransformationStudioProps) {
  const [columns, setColumns] = useState<string[]>(dataset.text_columns.slice(0, 1));
  const [instruction, setInstruction] = useState("");
  const [replacement, setReplacement] = useState("[REDACTED]");
  const [pattern, setPattern] = useState("");
  const [flags, setFlags] = useState<RegexFlag[]>([]);
  const [proposal, setProposal] = useState<RegexProposal>();

  const preview = useMutation({
    mutationFn: previewTransformation
  });
  const generation = useMutation({
    mutationFn: generateRegex,
    onSuccess: (result) => {
      setProposal(result);
      setPattern(result.pattern);
      setFlags(result.flags);
      preview.reset();
    }
  });

  const toggleColumn = (column: string) => {
    setColumns((current) =>
      current.includes(column)
        ? current.filter((name) => name !== column)
        : [...current, column]
    );
    setProposal(undefined);
    preview.reset();
  };

  const toggleFlag = (flag: RegexFlag) => {
    setFlags((current) =>
      current.includes(flag) ? current.filter((value) => value !== flag) : [...current, flag]
    );
    setProposal(undefined);
    preview.reset();
  };

  return (
    <section className="transform-studio" aria-labelledby="transform-heading">
      <header className="transform-heading">
        <div>
          <p className="eyebrow">AI-assisted transform</p>
          <h2 id="transform-heading">Describe, inspect, then approve</h2>
          <p>The model proposes a pattern. Deterministic code validates and previews it.</p>
        </div>
        <TrustStatus hasProposal={Boolean(proposal)} hasPreview={Boolean(preview.data)} />
      </header>

      <div className="transform-grid">
        <div className="transform-form">
          <fieldset>
            <legend>1. Target text columns</legend>
            <div className="checkbox-grid">
              {dataset.text_columns.map((column) => (
                <label key={column}>
                  <input
                    type="checkbox"
                    checked={columns.includes(column)}
                    onChange={() => toggleColumn(column)}
                  />
                  <span>{column}</span>
                </label>
              ))}
            </div>
          </fieldset>

          <label className="field-label" htmlFor="instruction">
            <span>2. Describe what to match</span>
            <textarea
              id="instruction"
              value={instruction}
              maxLength={1000}
              rows={3}
              placeholder="Find email addresses, including addresses inside Notes"
              onChange={(event) => {
                setInstruction(event.target.value);
                setProposal(undefined);
                preview.reset();
              }}
            />
          </label>

          <button
            className="primary-button"
            type="button"
            disabled={!columns.length || !instruction.trim() || generation.isPending}
            onClick={() => generation.mutate({ datasetId: dataset.id, instruction, columns })}
          >
            {generation.isPending ? "Generating proposal..." : "Generate regex proposal"}
          </button>
          {generation.error ? <InlineError message={generation.error.message} /> : null}

          <div className="form-divider" />

          <label className="field-label" htmlFor="pattern">
            <span>3. Inspect or edit the generated regex</span>
            <input
              id="pattern"
              className="code-input"
              value={pattern}
              spellCheck={false}
              placeholder="Generated pattern appears here"
              onChange={(event) => {
                setPattern(event.target.value);
                setProposal(undefined);
                preview.reset();
              }}
            />
          </label>

          <div className="flag-row">
            {supportedFlags.map((flag) => (
              <label key={flag.value}>
                <input
                  type="checkbox"
                  checked={flags.includes(flag.value)}
                  onChange={() => toggleFlag(flag.value)}
                />
                {flag.label}
              </label>
            ))}
          </div>

          <label className="field-label" htmlFor="replacement">
            <span>4. Replacement value</span>
            <input
              id="replacement"
              value={replacement}
              maxLength={512}
              onChange={(event) => {
                setReplacement(event.target.value);
                preview.reset();
              }}
            />
          </label>

          <button
            className="preview-button"
            type="button"
            disabled={!columns.length || !pattern || preview.isPending}
            onClick={() =>
              preview.mutate({ datasetId: dataset.id, pattern, replacement, columns, flags })
            }
          >
            {preview.isPending ? "Running safety checks..." : "Preview changes"}
          </button>
          {preview.error ? <InlineError message={preview.error.message} /> : null}
        </div>

        <aside className="proposal-panel" aria-label="Generated proposal details">
          {proposal ? <ProposalDetails proposal={proposal} /> : <ProposalEmptyState />}
        </aside>
      </div>

      {preview.data ? <PreviewResults result={preview.data} /> : null}
    </section>
  );
}

function TrustStatus({ hasProposal, hasPreview }: { hasProposal: boolean; hasPreview: boolean }) {
  const label = hasPreview
    ? "Trust gate passed"
    : hasProposal
      ? "Preview required"
      : "Awaiting proposal";
  return <span className={`trust-status ${hasPreview ? "passed" : ""}`}>{label}</span>;
}

function ProposalEmptyState() {
  return (
    <div className="proposal-empty">
      <span aria-hidden="true">{`{ }`}</span>
      <h3>No proposal yet</h3>
      <p>The regex, explanation, assumptions, and examples will remain visible and editable.</p>
    </div>
  );
}

function ProposalDetails({ proposal }: { proposal: RegexProposal }) {
  return (
    <div className="proposal-details">
      <div className="proposal-meta">
        <span>{proposal.provider}</span>
        <span>{proposal.model}</span>
        <strong>{Math.round(proposal.confidence * 100)}% confidence</strong>
      </div>
      <h3>Model interpretation</h3>
      <p>{proposal.explanation}</p>
      {proposal.assumptions.length ? (
        <>
          <h4>Assumptions</h4>
          <ul>{proposal.assumptions.map((value) => <li key={value}>{value}</li>)}</ul>
        </>
      ) : null}
      <div className="example-grid">
        <ExampleList title="Should match" values={proposal.positive_examples} />
        <ExampleList title="Should not match" values={proposal.negative_examples} />
      </div>
      <p className="data-boundary">Verified: {proposal.data_rows_sent} dataset rows sent to AI.</p>
    </div>
  );
}

function ExampleList({ title, values }: { title: string; values: string[] }) {
  if (!values.length) return null;
  return (
    <div>
      <h4>{title}</h4>
      {values.map((value) => <code key={value}>{value}</code>)}
    </div>
  );
}

function PreviewResults({ result }: { result: Awaited<ReturnType<typeof previewTransformation>> }) {
  return (
    <section className="preview-results" aria-labelledby="changes-heading">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Trust gate</p>
          <h3 id="changes-heading">Review every proposed change</h3>
        </div>
        <span>Showing up to {result.preview.length} affected rows</span>
      </div>

      <dl className="preview-metrics">
        <Metric label="Matches" value={result.match_count} />
        <Metric label="Affected rows" value={result.affected_rows} />
        <Metric label="Changed cells" value={result.changed_cells} />
        <Metric label="Total rows" value={result.total_rows} />
      </dl>

      {result.warnings.length ? (
        <div className="warning-panel" role="status">
          {result.warnings.map((warning) => <p key={warning}>{warning}</p>)}
        </div>
      ) : (
        <div className="passed-panel" role="status">Pattern compiled and executed within safety limits.</div>
      )}

      <div className="diff-list">
        {result.preview.map((row) =>
          row.changes.map((change) => (
            <article className="diff-card" key={`${row.row_index}-${change.column}`}>
              <header>
                <strong>Row {row.row_index + 1}</strong>
                <span>{change.column}</span>
              </header>
              <div className="diff-values">
                <div>
                  <small>Before</small>
                  <p>{highlightMatches(change.before, change.matches)}</p>
                </div>
                <div>
                  <small>After</small>
                  <p>{change.after}</p>
                </div>
              </div>
            </article>
          ))
        )}
      </div>
    </section>
  );
}

function highlightMatches(text: string, matches: MatchSpan[]) {
  const parts = [];
  let cursor = 0;
  matches.forEach((match, index) => {
    parts.push(text.slice(cursor, match.start));
    parts.push(<mark key={`${match.start}-${index}`}>{text.slice(match.start, match.end)}</mark>);
    cursor = match.end;
  });
  parts.push(text.slice(cursor));
  return parts;
}

function Metric({ label, value }: { label: string; value: number }) {
  return (
    <div>
      <dt>{label}</dt>
      <dd>{new Intl.NumberFormat("en-AU").format(value)}</dd>
    </div>
  );
}

function InlineError({ message }: { message: string }) {
  return <p className="inline-error compact" role="alert">{message}</p>;
}
