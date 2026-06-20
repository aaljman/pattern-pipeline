import type { Dataset, DatasetColumn } from "../api/datasets";

type DatasetProfileProps = {
  dataset: Dataset;
  onReplace: () => void;
};

export function DatasetProfile({ dataset, onReplace }: DatasetProfileProps) {
  return (
    <div className="dataset-profile">
      <header className="dataset-header">
        <div>
          <p className="eyebrow">Dataset ready</p>
          <h2>{dataset.original_name}</h2>
          <p>
            {formatNumber(dataset.row_count)} rows, {dataset.columns.length} columns
            {dataset.sheet_name ? `, sheet ${dataset.sheet_name}` : ""}
          </p>
        </div>
        <button className="secondary-button" type="button" onClick={onReplace}>
          Replace file
        </button>
      </header>

      <dl className="dataset-stats">
        <Stat label="File size" value={formatBytes(dataset.size_bytes)} />
        <Stat label="Text columns" value={String(dataset.text_columns.length)} />
        <Stat label="Preview rows" value={String(dataset.preview.length)} />
        <Stat label="Privacy" value="Local profiling" />
      </dl>

      <section className="schema-section" aria-labelledby="schema-heading">
        <div className="section-heading">
          <div>
            <p className="eyebrow">Schema</p>
            <h3 id="schema-heading">Choose with context</h3>
          </div>
          <span>{dataset.columns.length} detected</span>
        </div>
        <div className="column-chips">
          {dataset.columns.map((column) => (
            <ColumnChip column={column} key={column.name} />
          ))}
        </div>
      </section>

      <section className="preview-section" aria-labelledby="preview-heading">
        <div className="section-heading">
          <div>
            <p className="eyebrow">Source preview</p>
            <h3 id="preview-heading">Original data remains unchanged</h3>
          </div>
          <span>First {dataset.preview.length} rows</span>
        </div>
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th aria-label="Row number" scope="col">#</th>
                {dataset.columns.map((column) => (
                  <th key={column.name} scope="col">{column.name}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {dataset.preview.map((row, rowIndex) => (
                <tr key={rowIndex}>
                  <th scope="row">{rowIndex + 1}</th>
                  {dataset.columns.map((column) => (
                    <td key={column.name}>{displayValue(row[column.name])}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}

function ColumnChip({ column }: { column: DatasetColumn }) {
  return (
    <div className="column-chip">
      <span className={`type-dot ${column.type}`} aria-hidden="true" />
      <strong>{column.name}</strong>
      <span>{column.type}</span>
      {column.missing_count ? <small>{column.missing_count} missing</small> : null}
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt>{label}</dt>
      <dd>{value}</dd>
    </div>
  );
}

function formatNumber(value: number) {
  return new Intl.NumberFormat("en-AU").format(value);
}

function formatBytes(value: number) {
  if (value < 1024) return `${value} B`;
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`;
  return `${(value / (1024 * 1024)).toFixed(1)} MB`;
}

function displayValue(value: unknown) {
  if (value === null || value === undefined || value === "") {
    return <span className="empty-value">empty</span>;
  }
  return String(value);
}
