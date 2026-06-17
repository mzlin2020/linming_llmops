import { fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/api/apps", () => ({ listLanguageModels: vi.fn() }));

import { listLanguageModels } from "@/api/apps";
import { useAiModelStore } from "@/stores/ai-model-store";
import { renderWithProviders } from "@/test/render";
import type { LlmModel, LlmProvider } from "@/types/apps";

import { ModelPicker } from "./ModelPicker";

const model = (over: Partial<LlmModel> & { model_name: string }): LlmModel => ({
  label: {},
  features: [],
  context_window: 0,
  deprecated: false,
  model_type: "chat",
  ...over,
});

const providers: LlmProvider[] = [
  {
    name: "openai",
    label: { zh_Hans: "OpenAI" },
    description: {},
    models: [
      model({ model_name: "gpt-4o-mini", label: { zh_Hans: "GPT-4o mini" } }),
      model({ model_name: "gpt-legacy", deprecated: true }), // 弃用 → 应过滤
      model({ model_name: "img-gen", model_type: "text2img" }), // 非 chat → 应过滤
    ],
  },
];

beforeEach(() => {
  vi.clearAllMocks();
  useAiModelStore.getState().clearModel();
  vi.mocked(listLanguageModels).mockResolvedValue(providers);
});

describe("ModelPicker", () => {
  it("列出对话模型并过滤弃用/非 chat，默认选中「默认模型」", async () => {
    renderWithProviders(<ModelPicker />);
    expect(await screen.findByRole("option", { name: "GPT-4o mini" })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "默认模型" })).toBeInTheDocument();
    // 弃用与 text2img 模型不入列
    expect(screen.queryByRole("option", { name: "gpt-legacy" })).not.toBeInTheDocument();
    expect(screen.queryByRole("option", { name: "img-gen" })).not.toBeInTheDocument();
    expect((screen.getByLabelText("选择模型") as HTMLSelectElement).value).toBe("__default__");
  });

  it("选择某模型写入持久化 store，选回默认清空", async () => {
    renderWithProviders(<ModelPicker />);
    // 选项异步加载：先等模型 option 出现，再操作 select（否则 change 的目标值无对应 option 不生效）。
    await screen.findByRole("option", { name: "GPT-4o mini" });
    const select = screen.getByLabelText("选择模型") as HTMLSelectElement;

    fireEvent.change(select, { target: { value: "openai::gpt-4o-mini" } });
    await waitFor(() =>
      expect(useAiModelStore.getState()).toMatchObject({
        provider: "openai",
        model: "gpt-4o-mini",
      }),
    );

    fireEvent.change(select, { target: { value: "__default__" } });
    await waitFor(() =>
      expect(useAiModelStore.getState()).toMatchObject({ provider: null, model: null }),
    );
  });
});
