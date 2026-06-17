import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/api/ai", () => ({ suggestQuestions: vi.fn() }));

import { suggestQuestions } from "@/api/ai";

import type { ChatMessage } from "./chat-core";
import { useFollowups } from "./use-followups";

function Harness(props: { messages: ChatMessage[]; streaming: boolean; enabled: boolean }) {
  const followups = useFollowups(props);
  return (
    <ul>
      {followups.map((q) => (
        <li key={q}>{q}</li>
      ))}
    </ul>
  );
}

const userMsg: ChatMessage = { key: "u-1", role: "user", content: "问", status: "done" };
const liveAnswer = (id: number): ChatMessage => ({
  key: `a-${id}`,
  role: "assistant",
  content: "答",
  status: "done",
  id,
});
const histAnswer = (id: number): ChatMessage => ({
  key: `h-${id}-assistant`,
  role: "assistant",
  content: "答",
  status: "done",
  id,
});

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(suggestQuestions).mockResolvedValue(["追问A", "追问B"]);
});

describe("useFollowups", () => {
  it("开启且末条为实时助手回答 → 按 message_id 拉取并展示", async () => {
    render(<Harness messages={[userMsg, liveAnswer(7)]} streaming={false} enabled />);
    await waitFor(() => expect(suggestQuestions).toHaveBeenCalledWith(7));
    expect(await screen.findByText("追问A")).toBeInTheDocument();
    expect(screen.getByText("追问B")).toBeInTheDocument();
  });

  it("未开启（suggested_after_answer 关）→ 不拉取、不展示", () => {
    render(<Harness messages={[userMsg, liveAnswer(7)]} streaming={false} enabled={false} />);
    expect(suggestQuestions).not.toHaveBeenCalled();
    expect(screen.queryByRole("listitem")).toBeNull();
  });

  it("末条为加载来的历史回答（key h-）→ 不拉取（仅对本轮实时回答拉）", () => {
    render(<Harness messages={[userMsg, histAnswer(9)]} streaming={false} enabled />);
    expect(suggestQuestions).not.toHaveBeenCalled();
  });

  it("流式中 → 不拉取（等回答完成）", () => {
    render(<Harness messages={[userMsg, { ...liveAnswer(7), status: "streaming" }]} streaming enabled />);
    expect(suggestQuestions).not.toHaveBeenCalled();
  });
});
