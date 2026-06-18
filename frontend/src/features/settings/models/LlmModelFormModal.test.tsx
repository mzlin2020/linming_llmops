import { fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/api/admin-llm", () => ({
  createModel: vi.fn(),
  updateModel: vi.fn(),
}));

import { createModel } from "@/api/admin-llm";
import { renderWithProviders } from "@/test/render";

import { LlmModelFormModal } from "./LlmModelFormModal";

const mockCreate = vi.mocked(createModel);

beforeEach(() => {
  vi.clearAllMocks();
  mockCreate.mockResolvedValue({} as never);
});

describe("LlmModelFormModal", () => {
  it("新建：提交调 createModel(providerId, …)，携带勾选的能力", async () => {
    renderWithProviders(<LlmModelFormModal open providerId={7} model={null} onClose={() => {}} />);

    fireEvent.change(screen.getByLabelText("模型名（上游 model 参数）"), {
      target: { value: "my-model" },
    });
    fireEvent.click(screen.getByLabelText("tool_call"));
    fireEvent.click(screen.getByLabelText("streaming"));
    fireEvent.click(screen.getByRole("button", { name: "创建" }));

    await waitFor(() => expect(mockCreate).toHaveBeenCalledTimes(1));
    const [providerId, body] = mockCreate.mock.calls[0];
    expect(providerId).toBe(7);
    expect(body).toEqual(
      expect.objectContaining({
        model_name: "my-model",
        model_type: "chat",
        features: ["tool_call", "streaming"],
        context_window: 4096,
        enabled: true,
      }),
    );
    // 未填最大输出 → null
    expect(body.max_output_tokens).toBeNull();
  });
});
