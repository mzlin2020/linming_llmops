import { fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/api/settings", () => ({
  listApiKeys: vi.fn(),
  createApiKey: vi.fn(),
  updateApiKey: vi.fn(),
  deleteApiKey: vi.fn(),
}));

import { createApiKey, deleteApiKey, listApiKeys, updateApiKey } from "@/api/settings";
import { renderWithProviders } from "@/test/render";
import type { ApiKey } from "@/types/settings";

import { ApiKeysView } from "./ApiKeysView";

const mockList = vi.mocked(listApiKeys);
const mockCreate = vi.mocked(createApiKey);
const mockUpdate = vi.mocked(updateApiKey);
const mockDelete = vi.mocked(deleteApiKey);

const key = (over: Partial<ApiKey> = {}): ApiKey => ({
  id: 1,
  api_key: "ak-v1/abcdef123456",
  is_active: true,
  remark: "生产",
  created_at: 0,
  updated_at: 0,
  ...over,
});

beforeEach(() => {
  vi.clearAllMocks();
  mockList.mockResolvedValue([key()]);
  mockCreate.mockResolvedValue(key({ id: 2 }));
  mockUpdate.mockResolvedValue(key({ is_active: false }));
  mockDelete.mockResolvedValue(undefined);
});

describe("ApiKeysView", () => {
  it("渲染密钥", async () => {
    renderWithProviders(<ApiKeysView />);
    expect(await screen.findByText("ak-v1/abcdef123456")).toBeInTheDocument();
  });

  it("新建密钥 → 调 createApiKey", async () => {
    renderWithProviders(<ApiKeysView />);
    await screen.findByText("ak-v1/abcdef123456");
    fireEvent.click(screen.getByRole("button", { name: /新建密钥/ }));
    fireEvent.change(screen.getByLabelText("备注（可选）"), { target: { value: "测试" } });
    fireEvent.click(screen.getByRole("button", { name: "创建" }));
    await waitFor(() =>
      expect(mockCreate).toHaveBeenCalledWith(expect.objectContaining({ remark: "测试" })),
    );
  });

  it("启停开关 → 调 updateApiKey", async () => {
    renderWithProviders(<ApiKeysView />);
    await screen.findByText("ak-v1/abcdef123456");
    fireEvent.click(screen.getByRole("checkbox"));
    await waitFor(() =>
      expect(mockUpdate).toHaveBeenCalledWith(1, expect.objectContaining({ is_active: false })),
    );
  });

  it("删除走确认弹窗 → 调 deleteApiKey", async () => {
    renderWithProviders(<ApiKeysView />);
    await screen.findByText("ak-v1/abcdef123456");
    fireEvent.click(screen.getByLabelText("删除密钥 1"));
    fireEvent.click(screen.getByRole("button", { name: "删除" }));
    await waitFor(() => expect(mockDelete).toHaveBeenCalledWith(1));
  });
});
