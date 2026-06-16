import { fireEvent, screen, waitFor } from "@testing-library/react";
import { Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/api/datasets", () => ({
  listSegments: vi.fn(),
  createSegment: vi.fn(),
  updateSegment: vi.fn(),
  deleteSegment: vi.fn(),
  setSegmentEnabled: vi.fn(),
}));

import {
  createSegment,
  deleteSegment,
  listSegments,
  updateSegment,
} from "@/api/datasets";
import { renderWithProviders } from "@/test/render";

import { SegmentsView } from "./SegmentsView";

const mockList = vi.mocked(listSegments);
const mockCreate = vi.mocked(createSegment);
const mockUpdate = vi.mocked(updateSegment);
const mockDelete = vi.mocked(deleteSegment);

const seg = {
  id: 21,
  document_id: 11,
  dataset_id: 5,
  position: 1,
  content: "片段内容",
  keywords: ["kw"],
  character_count: 4,
  token_count: 2,
  hit_count: 0,
  enabled: true,
  status: "completed" as const,
  error: "",
  created_at: 0,
};

const page = () => ({
  list: [seg],
  paginator: { current_page: 1, page_size: 20, total_page: 1, total_record: 1 },
});

const renderView = () =>
  renderWithProviders(
    <Routes>
      <Route path="/datasets/:id/documents/:docId/segments" element={<SegmentsView />} />
    </Routes>,
    { route: "/datasets/5/documents/11/segments" },
  );

beforeEach(() => {
  vi.clearAllMocks();
  mockList.mockResolvedValue(page());
  mockCreate.mockResolvedValue(seg);
  mockUpdate.mockResolvedValue(seg);
  mockDelete.mockResolvedValue(undefined);
});

describe("SegmentsView", () => {
  it("渲染片段", async () => {
    renderView();
    expect(await screen.findByText("片段内容")).toBeInTheDocument();
  });

  it("新建片段 → 调 createSegment", async () => {
    renderView();
    await screen.findByText("片段内容");
    fireEvent.click(screen.getByRole("button", { name: /新建片段/ }));
    fireEvent.change(screen.getByLabelText("内容"), { target: { value: "新片段" } });
    fireEvent.click(screen.getByRole("button", { name: "创建" }));
    await waitFor(() =>
      expect(mockCreate).toHaveBeenCalledWith(5, 11, expect.objectContaining({ content: "新片段" })),
    );
  });

  it("编辑片段 → 调 updateSegment", async () => {
    renderView();
    await screen.findByText("片段内容");
    fireEvent.click(screen.getByLabelText("编辑片段 1"));
    fireEvent.change(screen.getByLabelText("内容"), { target: { value: "改后内容" } });
    fireEvent.click(screen.getByRole("button", { name: "保存" }));
    await waitFor(() =>
      expect(mockUpdate).toHaveBeenCalledWith(
        5,
        11,
        21,
        expect.objectContaining({ content: "改后内容" }),
      ),
    );
  });

  it("删除片段走确认弹窗 → 调 deleteSegment", async () => {
    renderView();
    await screen.findByText("片段内容");
    fireEvent.click(screen.getByLabelText("删除片段 1"));
    fireEvent.click(screen.getByRole("button", { name: "删除" }));
    await waitFor(() => expect(mockDelete).toHaveBeenCalledWith(5, 11, 21));
  });
});
