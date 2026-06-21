import { useRef, useState, type DragEvent } from "react";

type FileDropzoneProps = {
  error?: string;
  isUploading: boolean;
  onSelect: (file: File) => void;
};

const acceptedExtensions = [".csv", ".xlsx"];

export function FileDropzone({ error, isUploading, onSelect }: FileDropzoneProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [isDragging, setIsDragging] = useState(false);

  const chooseFile = (file?: File) => {
    if (file && !isUploading) {
      onSelect(file);
    }
  };

  const handleDrop = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    setIsDragging(false);
    chooseFile(event.dataTransfer.files[0]);
  };

  return (
    <div
      className={`drop-zone ${isDragging ? "dragging" : ""}`}
      onDragEnter={(event) => {
        event.preventDefault();
        setIsDragging(true);
      }}
      onDragLeave={() => setIsDragging(false)}
      onDragOver={(event) => event.preventDefault()}
      onDrop={handleDrop}
    >
      <input
        ref={inputRef}
        className="visually-hidden"
        type="file"
        aria-label="Upload CSV or XLSX file"
        accept={acceptedExtensions.join(",")}
        disabled={isUploading}
        onChange={(event) => {
          chooseFile(event.target.files?.[0]);
          event.target.value = "";
        }}
      />
      <span className="drop-icon" aria-hidden="true">{isUploading ? "..." : "+"}</span>
      <h2>{isUploading ? "Profiling your dataset" : "Start with a dataset"}</h2>
      <p>
        {isUploading
          ? "Reading columns, types, and a safe preview."
          : "Drop a CSV or XLSX file here, or choose one from your device."}
      </p>
      <button
        type="button"
        disabled={isUploading}
        onClick={() => inputRef.current?.click()}
      >
        {isUploading ? "Uploading..." : "Choose file"}
      </button>
      <small>Maximum 20 MB. Access expires after one hour.</small>
      {error ? <p className="inline-error" role="alert">{error}</p> : null}
    </div>
  );
}
