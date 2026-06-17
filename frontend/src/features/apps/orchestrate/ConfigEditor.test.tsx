import { fireEvent, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/api/apps", () => ({ listLanguageModels: vi.fn() }));
vi.mock("@/api/ai", () => ({
  optimizePresetPrompt: vi.fn(),
  suggestOpeningQuestions: vi.fn(),
}));
vi.mock("@/api/plugins", () => ({ listBuiltinTools: vi.fn(), listApiTools: vi.fn() }));
vi.mock("@/api/datasets", () => ({ listDatasets: vi.fn() }));
vi.mock("@/api/workflows", () => ({ listWorkflows: vi.fn() }));

import { listLanguageModels } from "@/api/apps";
import { listApiTools, listBuiltinTools } from "@/api/plugins";
import { listDatasets } from "@/api/datasets";
import { listWorkflows } from "@/api/workflows";
import { renderWithProviders } from "@/test/render";
import type { AppConfig } from "@/types/apps";

import { ConfigEditor } from "./ConfigEditor";

const config = (): AppConfig => ({
  model_config: { provider: "deepseek", model: "deepseek-chat", parameters: {} },
  dialog_round: 3,
  preset_prompt: "",
  tools: [],
  workflows: [],
  datasets: [],
  retrieval_config: {},
  long_term_memory: { enable: false },
  opening_statement: "",
  opening_questions: [],
  speech_to_text: { enable: false },
  text_to_speech: { enable: false },
  suggested_after_answer: { enable: true },
  review_config: {},
});

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(listBuiltinTools).mockResolvedValue([]);
  vi.mocked(listApiTools).mockResolvedValue({
    list: [],
    paginator: { current_page: 1, page_size: 50, total_page: 0, total_record: 0 },
  });
  vi.mocked(listDatasets).mockResolvedValue({
    list: [],
    paginator: { current_page: 1, page_size: 50, total_page: 0, total_record: 0 },
  });
  vi.mocked(listWorkflows).mockResolvedValue({
    list: [],
    paginator: { current_page: 1, page_size: 50, total_page: 0, total_record: 0 },
  });
  vi.mocked(listLanguageModels).mockResolvedValue([
    {
      name: "deepseek",
      label: { zh_Hans: "DeepSeek" },
      description: {},
      models: [
        {
          model_name: "deepseek-chat",
          label: { zh_Hans: "DeepSeek Chat" },
          features: [],
          context_window: 0,
          deprecated: false,
          model_type: "chat",
        },
        {
          model_name: "doubao-seedream",
          label: { zh_Hans: "火山生图" },
          features: [],
          context_window: 0,
          deprecated: false,
          model_type: "text2img",
        },
      ],
    },
  ]);
});

describe("ConfigEditor 模型下拉只显示对话模型", () => {
  it("chat 模型出现、text2img 图像模型被过滤", async () => {
    renderWithProviders(<ConfigEditor value={config()} onChange={() => {}} />);
    // 对话模型在下拉中可见
    expect(await screen.findByText("DeepSeek Chat")).toBeInTheDocument();
    // 图像模型（火山生图 / text2img）不应出现在对话模型下拉
    expect(screen.queryByText("火山生图")).toBeNull();
  });
});

describe("ConfigEditor 携带上下文轮数滑块", () => {
  it("拖动滑块以新轮数回调 onChange", () => {
    const onChange = vi.fn();
    renderWithProviders(<ConfigEditor value={config()} onChange={onChange} />);
    const slider = screen.getByRole("slider", { name: "对话轮数" });
    fireEvent.change(slider, { target: { value: "8" } });
    expect(onChange).toHaveBeenCalledWith(expect.objectContaining({ dialog_round: 8 }));
  });
});
