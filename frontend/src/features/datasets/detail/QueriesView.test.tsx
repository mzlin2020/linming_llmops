import { screen } from "@testing-library/react";
import { Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/api/datasets", () => ({ listDatasetQueries: vi.fn() }));

import { listDatasetQueries } from "@/api/datasets";
import { renderWithProviders } from "@/test/render";
import type { DatasetQuery } from "@/types/datasets";

import { QueriesView } from "./QueriesView";

const renderView = () =>
  renderWithProviders(
    <Routes>
      <Route path="/datasets/:id/queries" element={<QueriesView />} />
    </Routes>,
    { route: "/datasets/3/queries" },
  );

beforeEach(() => vi.clearAllMocks());

describe("QueriesView", () => {
  it("展示查询历史：文本 + 来源徽标（命中测试 / 应用对话）", async () => {
    const rows: DatasetQuery[] = [
      { id: 1, query: "什么是向量检索", source: "app", created_at: 1700000000 },
      { id: 2, query: "RAG 流程", source: "hit_testing", created_at: 1700000100 },
    ];
    vi.mocked(listDatasetQueries).mockResolvedValue(rows);
    renderView();
    expect(await screen.findByText("什么是向量检索")).toBeInTheDocument();
    expect(screen.getByText("应用对话")).toBeInTheDocument();
    expect(screen.getByText("命中测试")).toBeInTheDocument();
  });

  it("无记录时引导去命中测试", async () => {
    vi.mocked(listDatasetQueries).mockResolvedValue([]);
    renderView();
    expect(await screen.findByText(/还没有检索记录/)).toBeInTheDocument();
  });
});
