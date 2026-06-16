import { fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/sse/stream-sse", () => ({ streamSSE: vi.fn() }));
vi.mock("@/lib/http/client", () => ({ get: vi.fn(), post: vi.fn() }));

import { get } from "@/lib/http/client";
import { streamSSE } from "@/lib/sse/stream-sse";
import { renderWithProviders } from "@/test/render";

import { DebugChatPanel } from "./DebugChatPanel";

const mockStream = vi.mocked(streamSSE);
const mockGet = vi.mocked(get);

beforeEach(() => {
  vi.clearAllMocks();
  mockGet.mockResolvedValue({
    list: [],
    paginator: { current_page: 1, page_size: 20, total_page: 0, total_record: 0 },
  } as never);
});

describe("DebugChatPanel", () => {
  it("渲染空状态", async () => {
    renderWithProviders(<DebugChatPanel appId={7} />);
    expect(await screen.findByText(/在此预览当前草稿配置的对话效果/)).toBeInTheDocument();
  });

  it("发送 → 以 app 维度端点发起流式", async () => {
    mockStream.mockImplementation(async (_url, _body, { onEvent }) => {
      onEvent({ event: "agent_end", data: { status: "normal" } });
    });
    renderWithProviders(<DebugChatPanel appId={7} />);
    await screen.findByText(/在此预览当前草稿配置的对话效果/);

    fireEvent.change(screen.getByLabelText("消息输入"), { target: { value: "hi" } });
    fireEvent.click(screen.getByLabelText("发送"));

    await waitFor(() =>
      expect(mockStream).toHaveBeenCalledWith(
        "/apps/7/conversations",
        { query: "hi" },
        expect.objectContaining({ onEvent: expect.any(Function) }),
      ),
    );
  });
});
