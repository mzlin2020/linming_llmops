import { screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/api/apps", () => ({ listLanguageModels: vi.fn() }));

import { listLanguageModels } from "@/api/apps";
import { renderWithProviders } from "@/test/render";
import type { LlmProvider } from "@/types/apps";

import { ModelsView } from "./ModelsView";

const mockList = vi.mocked(listLanguageModels);

const provider: LlmProvider = {
  name: "openai",
  label: { zh_Hans: "OpenAI" },
  description: { zh_Hans: "OpenAI 兼容" },
  models: [
    {
      model_name: "gpt-4o-mini",
      label: { zh_Hans: "GPT-4o mini" },
      features: ["tool_call", "vision"],
      context_window: 128000,
      deprecated: false,
      model_type: "chat",
    },
  ],
};

beforeEach(() => {
  vi.clearAllMocks();
  mockList.mockResolvedValue([provider]);
});

describe("ModelsView", () => {
  it("渲染提供商与模型及能力标签", async () => {
    renderWithProviders(<ModelsView />);
    expect(await screen.findByText("OpenAI")).toBeInTheDocument();
    expect(screen.getByText("GPT-4o mini")).toBeInTheDocument();
    expect(screen.getByText("gpt-4o-mini")).toBeInTheDocument();
    expect(screen.getByText("工具调用")).toBeInTheDocument();
    expect(screen.getByText("视觉")).toBeInTheDocument();
  });
});
