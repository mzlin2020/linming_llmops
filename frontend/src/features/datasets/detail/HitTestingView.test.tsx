import { fireEvent, screen, waitFor } from "@testing-library/react";
import { Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/api/datasets", () => ({
  hitDataset: vi.fn(),
  listDatasetQueries: vi.fn(),
}));

import { hitDataset, listDatasetQueries } from "@/api/datasets";
import { renderWithProviders } from "@/test/render";

import { HitTestingView } from "./HitTestingView";

const mockHit = vi.mocked(hitDataset);
const mockQueries = vi.mocked(listDatasetQueries);

const renderView = () =>
  renderWithProviders(
    <Routes>
      <Route path="/datasets/:id/hit-testing" element={<HitTestingView />} />
    </Routes>,
    { route: "/datasets/5/hit-testing" },
  );

beforeEach(() => {
  vi.clearAllMocks();
  mockQueries.mockResolvedValue([]);
  mockHit.mockResolvedValue([
    {
      id: 1,
      document: { id: 11, name: "a.txt" },
      dataset_id: 5,
      score: 0.8,
      position: 1,
      content: "命中内容",
      keywords: ["k1"],
      character_count: 4,
      token_count: 2,
      hit_count: 0,
      enabled: true,
    },
  ]);
});

describe("HitTestingView", () => {
  it("检索 → 调 hitDataset 并渲染结果", async () => {
    renderView();
    fireEvent.change(screen.getByLabelText("检索内容"), { target: { value: "问题" } });
    fireEvent.click(screen.getByRole("button", { name: /检索/ }));
    await waitFor(() =>
      expect(mockHit).toHaveBeenCalledWith(5, {
        query: "问题",
        retrieval_strategy: "semantic",
        k: 4,
        score: 0.5,
      }),
    );
    expect(await screen.findByText("命中内容")).toBeInTheDocument();
  });

  it("全文检索禁用相关度阈值", () => {
    renderView();
    fireEvent.change(screen.getByLabelText("检索策略"), { target: { value: "full_text" } });
    expect(screen.getByLabelText("相关度阈值")).toBeDisabled();
  });
});
