import { fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/api/apps", () => ({ getSummary: vi.fn(), updateSummary: vi.fn() }));

import { getSummary, updateSummary } from "@/api/apps";
import { renderWithProviders } from "@/test/render";

import { LongTermMemoryModal } from "./LongTermMemoryModal";

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(getSummary).mockResolvedValue({ summary: "记住用户偏好简洁中文回答" });
  vi.mocked(updateSummary).mockResolvedValue(undefined);
});

describe("LongTermMemoryModal", () => {
  it("打开后展示当前长期记忆摘要", async () => {
    renderWithProviders(<LongTermMemoryModal appId={1} open onClose={() => {}} />);
    expect(await screen.findByDisplayValue("记住用户偏好简洁中文回答")).toBeInTheDocument();
  });

  it("点「清空记忆」以空串调用 updateSummary", async () => {
    renderWithProviders(<LongTermMemoryModal appId={1} open onClose={() => {}} />);
    await screen.findByDisplayValue("记住用户偏好简洁中文回答");
    fireEvent.click(screen.getByText("清空记忆"));
    await waitFor(() => expect(updateSummary).toHaveBeenCalledWith(1, ""));
  });
});
