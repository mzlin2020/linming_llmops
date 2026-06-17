import { fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/sse/stream-sse", () => ({ streamSSE: vi.fn() }));
vi.mock("@/lib/http/client", () => ({ get: vi.fn(), post: vi.fn() }));

import { get, post } from "@/lib/http/client";
import { streamSSE } from "@/lib/sse/stream-sse";
import { renderWithProviders } from "@/test/render";

import { DebugChatPanel } from "./DebugChatPanel";

const mockStream = vi.mocked(streamSSE);
const mockGet = vi.mocked(get);
const mockPost = vi.mocked(post);

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

  it("清空需二次确认：确认前不清空，确认后才调 delete-debug-conversation", async () => {
    // 有历史一轮 → 渲染出「清空」按钮
    mockGet.mockResolvedValue({
      list: [{ id: 1, query: "问", answer: "答", status: "normal", error: "" }],
      paginator: { current_page: 1, page_size: 20, total_page: 1, total_record: 1 },
    } as never);
    mockPost.mockResolvedValue(undefined as never);
    renderWithProviders(<DebugChatPanel appId={7} />);

    fireEvent.click(await screen.findByLabelText("清空调试对话"));
    expect(await screen.findByText("清空调试对话？")).toBeInTheDocument();
    expect(mockPost).not.toHaveBeenCalledWith("/apps/7/conversations/delete-debug-conversation");

    fireEvent.click(screen.getByRole("button", { name: "清空" }));
    await waitFor(() =>
      expect(mockPost).toHaveBeenCalledWith("/apps/7/conversations/delete-debug-conversation"),
    );
  });
});
