import { fireEvent, screen, waitFor } from "@testing-library/react";
import { Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/api/datasets", () => ({
  listDocuments: vi.fn(),
  setDocumentEnabled: vi.fn(),
  deleteDocument: vi.fn(),
  reindexDocument: vi.fn(),
  renameDocument: vi.fn(),
  createDocuments: vi.fn(),
  uploadFile: vi.fn(),
}));

import {
  deleteDocument,
  listDocuments,
  reindexDocument,
  setDocumentEnabled,
} from "@/api/datasets";
import { renderWithProviders } from "@/test/render";

import { DocumentsView } from "./DocumentsView";

const mockList = vi.mocked(listDocuments);
const mockSetEnabled = vi.mocked(setDocumentEnabled);
const mockDelete = vi.mocked(deleteDocument);
const mockReindex = vi.mocked(reindexDocument);

const page = () => ({
  list: [
    {
      id: 11,
      dataset_id: 5,
      name: "a.txt",
      position: 1,
      character_count: 10,
      token_count: 3,
      segment_count: 2,
      hit_count: 0,
      enabled: false,
      status: "completed" as const,
      error: "",
      batch: "b1",
      created_at: 0,
    },
  ],
  paginator: { current_page: 1, page_size: 20, total_page: 1, total_record: 1 },
});

const renderView = () =>
  renderWithProviders(
    <Routes>
      <Route path="/datasets/:id/documents" element={<DocumentsView />} />
    </Routes>,
    { route: "/datasets/5/documents" },
  );

beforeEach(() => {
  vi.clearAllMocks();
  mockList.mockResolvedValue(page());
  mockSetEnabled.mockResolvedValue(undefined);
  mockDelete.mockResolvedValue(undefined);
  mockReindex.mockResolvedValue(undefined as never);
});

describe("DocumentsView", () => {
  it("渲染文档行与状态徽标", async () => {
    renderView();
    expect(await screen.findByText("a.txt")).toBeInTheDocument();
    expect(screen.getByText("已完成")).toBeInTheDocument();
  });

  it("completed 文档启用 → 调 setDocumentEnabled", async () => {
    renderView();
    await screen.findByText("a.txt");
    fireEvent.click(screen.getByRole("checkbox"));
    await waitFor(() => expect(mockSetEnabled).toHaveBeenCalledWith(5, 11, true));
  });

  it("重新索引 → 调 reindexDocument", async () => {
    renderView();
    await screen.findByText("a.txt");
    fireEvent.click(screen.getByLabelText("重新索引 a.txt"));
    await waitFor(() => expect(mockReindex).toHaveBeenCalledWith(5, 11));
  });

  it("删除走确认弹窗 → 调 deleteDocument", async () => {
    renderView();
    await screen.findByText("a.txt");
    fireEvent.click(screen.getByLabelText("删除 a.txt"));
    fireEvent.click(screen.getByRole("button", { name: "删除" }));
    await waitFor(() => expect(mockDelete).toHaveBeenCalledWith(5, 11));
  });
});
