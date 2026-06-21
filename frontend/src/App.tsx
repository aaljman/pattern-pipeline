import { useState } from "react";
import { useMutation } from "@tanstack/react-query";

import { uploadDataset } from "./api/datasets";
import { DatasetProfile } from "./components/DatasetProfile";
import { FileDropzone } from "./components/FileDropzone";
import { OptionalTransforms } from "./components/OptionalTransforms";
import { TransformationStudio } from "./components/TransformationStudio";

const stages = ["Upload", "Transform", "Review", "Export"];

export function App() {
  const [hasCompletedRun, setHasCompletedRun] = useState(false);
  const [hasPreview, setHasPreview] = useState(false);
  const upload = useMutation({ mutationFn: uploadDataset });
  const activeStage = hasCompletedRun ? 3 : hasPreview ? 2 : upload.data ? 1 : 0;

  const resetDataset = () => {
    setHasCompletedRun(false);
    setHasPreview(false);
    upload.reset();
  };

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
          <li
            aria-current={index === activeStage ? "step" : undefined}
            className={index === activeStage ? "active" : index < activeStage ? "complete" : ""}
            key={stage}
          >
            <span>{index + 1}</span>
            {stage}
          </li>
        ))}
      </ol>

      <section className="workspace">
        {upload.data ? (
          <>
            <DatasetProfile dataset={upload.data} onReplace={resetDataset} />
            <TransformationStudio
              dataset={upload.data}
              onComplete={() => setHasCompletedRun(true)}
              onPreview={() => setHasPreview(true)}
              onPreviewInvalidated={() => {
                setHasPreview(false);
                setHasCompletedRun(false);
              }}
            />
            <OptionalTransforms
              dataset={upload.data}
              onComplete={() => setHasCompletedRun(true)}
              onPreview={() => setHasPreview(true)}
              onPreviewInvalidated={() => {
                setHasPreview(false);
                setHasCompletedRun(false);
              }}
            />
          </>
        ) : (
          <FileDropzone
            error={upload.error?.message}
            isUploading={upload.isPending}
            onSelect={(file) => upload.mutate(file)}
          />
        )}
      </section>
    </main>
  );
}
