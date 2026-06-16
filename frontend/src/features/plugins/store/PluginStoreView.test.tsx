import { fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/api/plugins", () => ({
  listStorePlugins: vi.fn(),
  addStorePlugin: vi.fn(),
}));

import { addStorePlugin, listStorePlugins } from "@/api/plugins";
import { renderWithProviders } from "@/test/render";

import { PluginStoreView } from "./PluginStoreView";

const mockList = vi.mocked(listStorePlugins);
const mockAdd = vi.mocked(addStorePlugin);

const page = () => ({
  list: [
    { id: 1, name: "A 插件", icon: "", description: "", tools: [], added: false, created_at: 0 },
    { id: 2, name: "B 插件", icon: "", description: "", tools: [], added: true, created_at: 0 },
  ],
  paginator: { current_page: 1, page_size: 12, total_page: 1, total_record: 2 },
});

beforeEach(() => {
  vi.clearAllMocks();
  mockList.mockResolvedValue(page());
  mockAdd.mockResolvedValue(undefined);
});

describe("PluginStoreView", () => {
  it("已添加项禁用「已添加」按钮", async () => {
    renderWithProviders(<PluginStoreView />);
    await screen.findByText("B 插件");
    expect(screen.getByRole("button", { name: "已添加" })).toBeDisabled();
  });

  it("点「添加」→ 调 addStorePlugin(public_id)", async () => {
    renderWithProviders(<PluginStoreView />);
    await screen.findByText("A 插件");

    fireEvent.click(screen.getByRole("button", { name: "添加" }));

    await waitFor(() => expect(mockAdd).toHaveBeenCalledWith(1));
  });
});
