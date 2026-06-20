const stages = ["Upload", "Transform", "Review", "Export"];

export function App() {
  return (
    <main className="shell">
      <header className="masthead">
        <a className="brand" href="/" aria-label="Pattern Pipeline home">
          <span className="brand-mark" aria-hidden="true" />
          <span>Pattern Pipeline</span>
        </a>
        <span className="privacy-badge">0 data rows sent to AI</span>
      </header>

      <section className="hero">
        <p className="eyebrow">Trust-first data transformation</p>
        <h1>Describe the change. Inspect every match.</h1>
        <p>
          Turn natural-language requests into safe, reviewable transformations
          for CSV and Excel files.
        </p>
      </section>

      <ol className="pipeline" aria-label="Transformation progress">
        {stages.map((stage, index) => (
          <li className={index === 0 ? "active" : ""} key={stage}>
            <span>{index + 1}</span>
            {stage}
          </li>
        ))}
      </ol>

      <section className="workspace">
        <div className="drop-zone">
          <span className="drop-icon" aria-hidden="true">+</span>
          <h2>Start with a dataset</h2>
          <p>Drop a CSV or XLSX file here, or choose one from your device.</p>
          <button type="button">Choose file</button>
          <small>Files are private and automatically expire.</small>
        </div>
      </section>
    </main>
  );
}
