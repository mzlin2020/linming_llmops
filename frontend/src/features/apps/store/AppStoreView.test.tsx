import { fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/api/apps", () => ({
  getAppStore: vi.fn(),
  addStoreApp: vi.fn(),
}));

import { addStoreApp, getAppStore } from "@/api/apps";
import { renderWithProviders } from "@/test/render";
import type { PublicAppBrief } from "@/types/apps";

import { AppStoreView } from "./AppStoreView";

const mockStore = vi.mocked(getAppStore);
const mockAdd = vi.mocked(addStoreApp);

const brief = (over: Partial<PublicAppBrief> = {}): PublicAppBrief => ({
  id: 10,
  name: "翻译助手",
  icon: "",
  description: "中英互译",
  model_provider: "openai",
  model_name: "gpt-4o-mini",
  tool_count: 2,
  added: false,
  created_at: 0,
  ...over,
});

const page = (list: PublicAppBrief[]) => ({
  list,
  paginator: { current_page: 1, page_size: 12, total_page: 1, total_record: list.length },
});

beforeEach(() => {
  vi.clearAllMocks();
  mockStore.mockResolvedValue(page([brief()]));
  mockAdd.mockResolvedValue({} as never);
});

describe("AppStoreView", () => {
  it("渲染商店应用卡片", async () => {
    renderWithProviders(<AppStoreView />);
    expect(await screen.findByText("翻译助手")).toBeInTheDocument();
  });

  it("未添加 → 点添加调 addStoreApp", async () => {
    renderWithProviders(<AppStoreView />);
    await screen.findByText("翻译助手");
    fireEvent.click(screen.getByRole("button", { name: /添加/ }));
    await waitFor(() => expect(mockAdd).toHaveBeenCalledWith(10));
  });

  it("已添加 → 按钮禁用且显示已添加", async () => {
    mockStore.mockResolvedValue(page([brief({ added: true })]));
    renderWithProviders(<AppStoreView />);
    const btn = await screen.findByRole("button", { name: /已添加/ });
    expect(btn).toBeDisabled();
  });
});
