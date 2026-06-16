import { fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/sse/stream-sse", () => ({ streamSSE: vi.fn() }));
vi.mock("./api", () => ({
  CHAT_URL: "/assistant-agent/chat",
  fetchHistory: vi.fn(),
  clearConversation: vi.fn(),
  stopTask: vi.fn(),
}));

import { streamSSE } from "@/lib/sse/stream-sse";
import { renderWithProviders } from "@/test/render";

import { AssistantChat } from "./AssistantChat";
import { clearConversation, fetchHistory, stopTask } from "./api";
import type { ChatMessage } from "./types";

const mockStream = vi.mocked(streamSSE);
const mockFetchHistory = vi.mocked(fetchHistory);
const mockStop = vi.mocked(stopTask);
const mockClear = vi.mocked(clearConversation);

beforeEach(() => {
  vi.clearAllMocks();
  mockFetchHistory.mockResolvedValue([]);
  mockStop.mockResolvedValue(undefined);
  mockClear.mockResolvedValue(undefined);
});

function send(text: string) {
  fireEvent.change(screen.getByLabelText("消息输入"), { target: { value: text } });
  fireEvent.click(screen.getByLabelText("发送"));
}

async function renderReady() {
  renderWithProviders(<AssistantChat />);
  await waitFor(() => expect(mockFetchHistory).toHaveBeenCalled());
}

describe("AssistantChat", () => {
  it("发送后流式累加助手回复并收尾为完成态", async () => {
    mockStream.mockImplementation(async (_url, _body, { onEvent }) => {
      onEvent({ event: "ping", data: { task_id: "t1" } });
      onEvent({ event: "message", data: { delta: "你好" } });
      onEvent({ event: "message", data: { delta: "，世界" } });
      onEvent({ event: "agent_end", data: { status: "normal" } });
    });
    await renderReady();

    send("hi");

    expect(await screen.findByText("你好，世界")).toBeInTheDocument();
    expect(mockStream).toHaveBeenCalledWith(
      "/assistant-agent/chat",
      { query: "hi" },
      expect.objectContaining({ onEvent: expect.any(Function) }),
    );
  });

  it("流式中点停止 → 调真实 stop 端点并标记已停止", async () => {
    mockStream.mockImplementation((_url, _body, { onEvent, signal }) => {
      onEvent({ event: "ping", data: { task_id: "t1" } });
      onEvent({ event: "message", data: { delta: "思考中" } });
      return new Promise<void>((resolve) => {
        signal?.addEventListener("abort", () => resolve());
      });
    });
    await renderReady();

    send("hi");

    fireEvent.click(await screen.findByLabelText("停止生成"));
    await waitFor(() => expect(mockStop).toHaveBeenCalledWith("t1"));
    expect(await screen.findByText(/已停止生成/)).toBeInTheDocument();
  });

  it("空状态点击建议问题 → 以该问题发起流式", async () => {
    mockStream.mockImplementation(async (_url, _body, { onEvent }) => {
      onEvent({ event: "agent_end", data: { status: "normal" } });
    });
    await renderReady();

    fireEvent.click(screen.getByText("什么是 RAG？"));

    await waitFor(() =>
      expect(mockStream).toHaveBeenCalledWith(
        "/assistant-agent/chat",
        { query: "什么是 RAG？" },
        expect.anything(),
      ),
    );
  });

  it("挂载时渲染服务端历史", async () => {
    const history: ChatMessage[] = [
      { key: "h-1-user", role: "user", content: "历史问题", status: "done" },
      { key: "h-1-assistant", role: "assistant", content: "历史回答", status: "done" },
    ];
    mockFetchHistory.mockResolvedValue(history);

    renderWithProviders(<AssistantChat />);

    expect(await screen.findByText("历史回答")).toBeInTheDocument();
    expect(screen.getByText("历史问题")).toBeInTheDocument();
  });

  it("清空 → 调 delete-conversation 并回到空状态", async () => {
    mockFetchHistory.mockResolvedValue([
      { key: "h-1-user", role: "user", content: "历史问题", status: "done" },
      { key: "h-1-assistant", role: "assistant", content: "历史回答", status: "done" },
    ]);
    renderWithProviders(<AssistantChat />);
    await screen.findByText("历史回答");

    fireEvent.click(screen.getByLabelText("清空对话"));

    await waitFor(() => expect(mockClear).toHaveBeenCalled());
    expect(await screen.findByText(/我是你的 AI 助手/)).toBeInTheDocument();
  });
});
