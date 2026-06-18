import { fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/api/apps", () => ({ createApp: vi.fn() }));

import { createApp } from "@/api/apps";
import { renderWithProviders } from "@/test/render";
import type { AppListItem } from "@/types/apps";

import { AppFormModal } from "./AppFormModal";

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(createApp).mockResolvedValue({ id: 9 } as AppListItem);
});

describe("AppFormModal 新建应用", () => {
  it("填名称+人设提示词 → 以 preset_prompt 调 createApp", async () => {
    renderWithProviders(<AppFormModal open onClose={() => {}} />);
    fireEvent.change(screen.getByLabelText("名称"), { target: { value: "周报助手" } });
    fireEvent.change(screen.getByLabelText("人设 / 提示词（可选）"), {
      target: { value: "你是一个周报助手" },
    });
    fireEvent.click(screen.getByRole("button", { name: "创建" }));

    await waitFor(() =>
      expect(createApp).toHaveBeenCalledWith(
        expect.objectContaining({ name: "周报助手", preset_prompt: "你是一个周报助手" }),
      ),
    );
  });

  it("人设留空 → preset_prompt 传 undefined（不发空串）", async () => {
    renderWithProviders(<AppFormModal open onClose={() => {}} />);
    fireEvent.change(screen.getByLabelText("名称"), { target: { value: "客服助手" } });
    fireEvent.click(screen.getByRole("button", { name: "创建" }));

    await waitFor(() =>
      expect(createApp).toHaveBeenCalledWith(
        expect.objectContaining({ name: "客服助手", preset_prompt: undefined }),
      ),
    );
  });
});
