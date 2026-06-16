import { fireEvent } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { renderWithProviders } from "@/test/render";

import { FileDropzone } from "./FileDropzone";

describe("FileDropzone", () => {
  it("选择文件发出 File[]", () => {
    const onFiles = vi.fn();
    const { container } = renderWithProviders(
      <FileDropzone accept={["txt"]} onFiles={onFiles} />,
    );
    const input = container.querySelector('input[type="file"]') as HTMLInputElement;
    const file = new File(["hello"], "a.txt", { type: "text/plain" });
    fireEvent.change(input, { target: { files: [file] } });
    expect(onFiles).toHaveBeenCalledTimes(1);
    expect(onFiles.mock.calls[0][0][0].name).toBe("a.txt");
  });
});
