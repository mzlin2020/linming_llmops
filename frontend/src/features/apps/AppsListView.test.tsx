import { fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/api/apps", () => ({
  listApps: vi.fn(),
  copyApp: vi.fn(),
  deleteApp: vi.fn(),
  createApp: vi.fn(),
}));

import { copyApp, createApp, deleteApp, listApps } from "@/api/apps";
import { renderWithProviders } from "@/test/render";
import type { AppListItem } from "@/types/apps";

import { AppsListView } from "./AppsListView";

const mockList = vi.mocked(listApps);
const mockCopy = vi.mocked(copyApp);
const mockDelete = vi.mocked(deleteApp);
const mockCreate = vi.mocked(createApp);

const app = (over: Partial<AppListItem> = {}): AppListItem => ({
  id: 1,
  user_id: 1,
  name: "客服助手",
  description: "回答客服问题",
  icon: "",
  status: "draft",
  is_default: false,
  is_assistant_agent: false,
  created_at: null,
  updated_at: null,
  preset_prompt: "",
  model_config: { provider: "openai", model: "gpt-4o-mini", parameters: {} },
  dialog_round: 3,
  ...over,
});

beforeEach(() => {
  vi.clearAllMocks();
  mockList.mockResolvedValue([app()]);
  mockCopy.mockResolvedValue(app({ id: 2, name: "客服助手 副本" }));
  mockDelete.mockResolvedValue(undefined);
  mockCreate.mockResolvedValue(app({ id: 9, name: "新应用" }));
});

describe("AppsListView", () => {
  it("渲染应用卡片", async () => {
    renderWithProviders(<AppsListView />);
    expect(await screen.findByText("客服助手")).toBeInTheDocument();
  });

  it("新建应用 → 提交调 createApp", async () => {
    renderWithProviders(<AppsListView />);
    await screen.findByText("客服助手");
    fireEvent.click(screen.getByRole("button", { name: /新建应用/ }));
    fireEvent.change(screen.getByLabelText("名称"), { target: { value: "新应用" } });
    fireEvent.click(screen.getByRole("button", { name: "创建" }));
    await waitFor(() =>
      expect(mockCreate).toHaveBeenCalledWith(expect.objectContaining({ name: "新应用" })),
    );
  });

  it("删除应用走确认弹窗 → 调 deleteApp", async () => {
    renderWithProviders(<AppsListView />);
    await screen.findByText("客服助手");
    fireEvent.click(screen.getByLabelText("删除 客服助手"));
    fireEvent.click(screen.getByRole("button", { name: "删除" }));
    await waitFor(() => expect(mockDelete).toHaveBeenCalledWith(1));
  });

  it("复制应用 → 调 copyApp", async () => {
    renderWithProviders(<AppsListView />);
    await screen.findByText("客服助手");
    fireEvent.click(screen.getByLabelText("复制 客服助手"));
    await waitFor(() => expect(mockCopy).toHaveBeenCalledWith(1));
  });
});
