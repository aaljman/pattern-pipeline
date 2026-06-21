import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { FileDropzone } from "./FileDropzone";

describe("FileDropzone", () => {
  it("passes the selected file to the upload handler", async () => {
    const user = userEvent.setup();
    const onSelect = vi.fn();
    const file = new File(["name\nAda\n"], "customers.csv", { type: "text/csv" });
    const { container } = render(
      <FileDropzone isUploading={false} onSelect={onSelect} />
    );

    const input = container.querySelector<HTMLInputElement>('input[type="file"]')!;
    await user.upload(input, file);

    expect(onSelect).toHaveBeenCalledWith(file);
  });

  it("handles a dropped file and exposes server errors accessibly", () => {
    const onSelect = vi.fn();
    const file = new File(["name\nAda\n"], "customers.csv", { type: "text/csv" });
    const { container } = render(
      <FileDropzone
        error="Only CSV and XLSX files are supported."
        isUploading={false}
        onSelect={onSelect}
      />
    );

    fireEvent.drop(container.firstElementChild!, {
      dataTransfer: { files: [file] }
    });

    expect(onSelect).toHaveBeenCalledWith(file);
    expect(screen.getByRole("alert")).toHaveTextContent("Only CSV and XLSX");
  });

  it("disables selection while an upload is pending", () => {
    const { container } = render(
      <FileDropzone isUploading onSelect={vi.fn()} />
    );

    expect(screen.getByRole("button", { name: "Uploading..." })).toBeDisabled();
    expect(container.querySelector('input[type="file"]')).toBeDisabled();
  });
});
