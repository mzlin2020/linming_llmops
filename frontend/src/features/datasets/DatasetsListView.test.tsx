import { fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/api/datasets", () => ({
  listDatasets: vi.fn(),
  deleteDataset: vi.fn(),
  createDataset: vi.fn(),
  updateDataset: vi.fn(),
}));

import { createDataset, deleteDataset, listDatasets } from "@/api/datasets";
import { renderWithProviders } from "@/test/render";

import { DatasetsListView } from "./DatasetsListView";

const mockList = vi.mocked(listDatasets);
const mockDelete = vi.mocked(deleteDataset);
const mockCreate = vi.mocked(createDataset);

const page = () => ({
  list: [
    {
      id: 7,
      name: "手册",
      icon: "",
      description: "产品手册",
      document_count: 2,
      character_count: 100,
      hit_count: 5,
      created_at: 0,
      updated_at: 0,
    },
  ],
  paginator: { current_page: 1, page_size: 12, total_page: 1, total_record: 1 },
});

beforeEach(() => {
  vi.clearAllMocks();
  mockList.mockResolvedValue(page());
  mockDelete.mockResolvedValue(undefined);
  mockCreate.mockResolvedValue({ id: 99 });
});

describe("DatasetsListView", () => {
  it("渲染知识库卡片", async () => {
    renderWithProviders(<DatasetsListView />);
    expect(await screen.findByText("手册")).toBeInTheDocument();
  });

  it("删除走确认弹窗 → 调 deleteDataset", async () => {
    renderWithProviders(<DatasetsListView />);
    await screen.findByText("手册");
    fireEvent.click(screen.getByLabelText("删除 手册"));
    fireEvent.click(screen.getByRole("button", { name: "删除" }));
    await waitFor(() => expect(mockDelete).toHaveBeenCalledWith(7));
  });

  it("新建填表提交 → 调 createDataset", async () => {
    renderWithProviders(<DatasetsListView />);
    await screen.findByText("手册");
    fireEvent.click(screen.getByRole("button", { name: /新建知识库/ }));
    fireEvent.change(screen.getByLabelText("名称"), { target: { value: "新库" } });
    fireEvent.click(screen.getByRole("button", { name: "创建" }));
    await waitFor(() =>
      expect(mockCreate).toHaveBeenCalledWith({ name: "新库", icon: "", description: "" }),
    );
  });
});
