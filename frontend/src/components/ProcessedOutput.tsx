type ProcessedOutputProps = {
  columns: string[];
  rows: Record<string, unknown>[];
};

export function ProcessedOutput({ columns, rows }: ProcessedOutputProps) {
  return (
    <section className="processed-output" aria-labelledby="processed-output-heading">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Processed output</p>
          <h3 id="processed-output-heading">Applied replacement results</h3>
        </div>
        <span>First {rows.length} rows</span>
      </div>
      <div className="table-scroll">
        <table>
          <thead>
            <tr>
              <th aria-label="Row number" scope="col">#</th>
              {columns.map((column) => <th key={column} scope="col">{column}</th>)}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, rowIndex) => (
              <tr key={rowIndex}>
                <th scope="row">{rowIndex + 1}</th>
                {columns.map((column) => (
                  <td key={column}>{displayValue(row[column])}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function displayValue(value: unknown) {
  if (value === null || value === undefined || value === "") {
    return <span className="empty-value">empty</span>;
  }
  return typeof value === "object" ? JSON.stringify(value) : String(value);
}
