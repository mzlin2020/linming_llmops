import { fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/api/admin-llm", () => ({
  createProvider: vi.fn(),
  updateProvider: vi.fn(),
}));

import { createProvider } from "@/api/admin-llm";
import { renderWithProviders } from "@/test/render";

import { LlmProviderFormModal } from "./LlmProviderFormModal";

const mockCreate = vi.mocked(createProvider);

beforeEach(() => {
  vi.clearAllMocks();
  mockCreate.mockResolvedValue({} as never);
});

describe("LlmProviderFormModal", () => {
  it("新建：提交调 createProvider，携带 name/protocol/默认类型", async () => {
    renderWithProviders(
      <LlmProviderFormModal open protocols={["openai", "anthropic"]} onClose={() => {}} />,
    );

    fireEvent.change(screen.getByLabelText("标识（唯一）"), { target: { value: "my_gw" } });
    fireEvent.change(screen.getByLabelText("显示名"), { target: { value: "我的网关" } });
    fireEvent.change(screen.getByLabelText("Base URL"), {
      target: { value: "https://gw.example/v1" },
    });
    fireEvent.click(screen.getByRole("button", { name: "创建" }));

    await waitFor(() => expect(mockCreate).toHaveBeenCalledTimes(1));
    expect(mockCreate).toHaveBeenCalledWith(
      expect.objectContaining({
        name: "my_gw",
        protocol: "openai",
        base_url: "https://gw.example/v1",
        label: { zh_Hans: "我的网关" },
        supported_model_types: ["chat"],
        enabled: true,
      }),
    );
    // 未填密钥 → 不带 api_key 字段
    expect(mockCreate.mock.calls[0][0]).not.toHaveProperty("api_key");
  });

  it("非法标识（含大写）→ 校验拦截，不调接口", async () => {
    renderWithProviders(<LlmProviderFormModal open protocols={["openai"]} onClose={() => {}} />);

    fireEvent.change(screen.getByLabelText("标识（唯一）"), { target: { value: "BadName" } });
    fireEvent.click(screen.getByRole("button", { name: "创建" }));

    expect(await screen.findByText(/仅小写字母/)).toBeInTheDocument();
    expect(mockCreate).not.toHaveBeenCalled();
  });
});
