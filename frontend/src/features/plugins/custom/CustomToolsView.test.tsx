import { fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/api/plugins", () => ({
  listApiTools: vi.fn(),
  deleteApiTool: vi.fn(),
  publishApiTool: vi.fn(),
}));

import { deleteApiTool, listApiTools, publishApiTool } from "@/api/plugins";
import { renderWithProviders } from "@/test/render";

import { CustomToolsView } from "./CustomToolsView";

const mockList = vi.mocked(listApiTools);
const mockDelete = vi.mocked(deleteApiTool);
const mockPublish = vi.mocked(publishApiTool);

const page = () => ({
  list: [
    {
      id: 3,
      name: "天气",
      icon: "",
      description: "查天气",
      headers: [],
      tools: [{ id: 1, name: "t", description: "", inputs: [] }],
      is_public: false,
      created_at: 0,
    },
  ],
  paginator: { current_page: 1, page_size: 12, total_page: 1, total_record: 1 },
});

beforeEach(() => {
  vi.clearAllMocks();
  mockList.mockResolvedValue(page());
  mockDelete.mockResolvedValue(undefined);
  mockPublish.mockResolvedValue(undefined);
});

describe("CustomToolsView", () => {
  it("渲染列表卡片", async () => {
    renderWithProviders(<CustomToolsView />);
    expect(await screen.findByText("天气")).toBeInTheDocument();
  });

  it("删除走确认弹窗 → 调 deleteApiTool", async () => {
    renderWithProviders(<CustomToolsView />);
    await screen.findByText("天气");

    fireEvent.click(screen.getByLabelText("删除 天气"));
    fireEvent.click(screen.getByRole("button", { name: "删除" }));

    await waitFor(() => expect(mockDelete).toHaveBeenCalledWith(3));
  });

  it("上架切换 → 调 publishApiTool(is_public=true)", async () => {
    renderWithProviders(<CustomToolsView />);
    await screen.findByText("天气");

    fireEvent.click(screen.getByRole("button", { name: "上架" }));

    await waitFor(() => expect(mockPublish).toHaveBeenCalledWith(3, true));
  });
});
