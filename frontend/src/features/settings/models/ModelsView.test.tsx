import { screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/api/apps", () => ({ listLanguageModels: vi.fn() }));
vi.mock("@/api/admin-llm", () => ({
  listLlmProtocols: vi.fn(),
  listAdminProviders: vi.fn(),
}));

import { listLlmProtocols, listAdminProviders } from "@/api/admin-llm";
import { listLanguageModels } from "@/api/apps";
import { renderWithProviders } from "@/test/render";
import type { AdminLlmProvider } from "@/types/admin-llm";
import type { LlmProvider } from "@/types/apps";

import { ModelsView } from "./ModelsView";

const mockProtocols = vi.mocked(listLlmProtocols);
const mockAdmin = vi.mocked(listAdminProviders);
const mockReadonly = vi.mocked(listLanguageModels);

const readonlyProvider: LlmProvider = {
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

const adminProvider: AdminLlmProvider = {
  id: 1,
  name: "openai",
  label: { zh_Hans: "OpenAI" },
  description: {},
  icon: "",
  background: "",
  supported_model_types: ["chat"],
  protocol: "openai",
  multi_channel: false,
  base_url: "https://api.openai.com/v1",
  has_api_key: false,
  api_key_mask: "(环境变量 OPENAI_API_KEY)",
  api_key_env: "OPENAI_API_KEY",
  enabled: true,
  sort: 10,
  models: [
    {
      id: 11,
      provider_id: 1,
      model_name: "gpt-4o-mini",
      label: { zh_Hans: "GPT-4o mini" },
      model_type: "chat",
      features: ["tool_call"],
      context_window: 128000,
      max_output_tokens: 16384,
      parameter_rules: [],
      pricing: null,
      deprecated: false,
      admin_only: false,
      is_default: true,
      enabled: true,
      sort: 1,
    },
  ],
};

beforeEach(() => {
  vi.clearAllMocks();
  mockReadonly.mockResolvedValue([readonlyProvider]);
  mockAdmin.mockResolvedValue([adminProvider]);
});

describe("ModelsView", () => {
  it("开关关（protocols 403）→ 只读目录，不显示管理按钮", async () => {
    mockProtocols.mockRejectedValue(new Error("403"));
    renderWithProviders(<ModelsView />);

    expect(await screen.findByText("GPT-4o mini")).toBeInTheDocument();
    expect(screen.getByText(/只读/)).toBeInTheDocument();
    expect(screen.getByText("工具调用")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /新增提供商/ })).toBeNull();
  });

  it("开关开（protocols 成功）→ 管理模式，含增删改入口", async () => {
    mockProtocols.mockResolvedValue(["openai", "anthropic"]);
    renderWithProviders(<ModelsView />);

    expect(await screen.findByText("gpt-4o-mini")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /新增提供商/ })).toBeInTheDocument();
    expect(screen.getAllByText("openai").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByLabelText("编辑提供商 openai")).toBeInTheDocument();
    expect(screen.getByLabelText("删除模型 gpt-4o-mini")).toBeInTheDocument();
    expect(mockAdmin).toHaveBeenCalled();
  });
});
