import { fireEvent, screen, waitFor } from "@testing-library/react";
import { Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/api/apps", () => ({
  getApp: vi.fn(),
  updateDraftConfig: vi.fn(),
  publishApp: vi.fn(),
  cancelPublishApp: vi.fn(),
  setAppPublic: vi.fn(),
}));

// 子组件以轻量桩替身，隔离编排页本身的 加载/保存/发布 逻辑。
vi.mock("./ConfigEditor", () => ({
  ConfigEditor: ({
    value,
    onChange,
  }: {
    value: { dialog_round: number };
    onChange: (n: unknown) => void;
  }) => (
    <button type="button" onClick={() => onChange({ ...value, dialog_round: value.dialog_round + 1 })}>
      改一处配置
    </button>
  ),
}));
vi.mock("./DebugChatPanel", () => ({ DebugChatPanel: () => <div>debug-chat</div> }));
vi.mock("./PublishHistoryModal", () => ({ PublishHistoryModal: () => null }));

import { cancelPublishApp, getApp, publishApp, setAppPublic, updateDraftConfig } from "@/api/apps";
import { renderWithProviders } from "@/test/render";
import type { AppConfig, AppDetail } from "@/types/apps";

import { OrchestrationPage } from "./OrchestrationPage";

const mockGet = vi.mocked(getApp);
const mockUpdate = vi.mocked(updateDraftConfig);
const mockPublish = vi.mocked(publishApp);
void cancelPublishApp;
void setAppPublic;

const config = (): AppConfig => ({
  model_config: { provider: "openai", model: "gpt-4o-mini", parameters: {} },
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

const detail = (over: Partial<AppDetail> = {}): AppDetail => ({
  id: 7,
  user_id: 1,
  name: "客服助手",
  description: "",
  icon: "",
  status: "draft",
  is_default: false,
  is_assistant_agent: false,
  created_at: null,
  updated_at: null,
  preset_prompt: "",
  model_config: { provider: "openai", model: "gpt-4o-mini", parameters: {} },
  dialog_round: 3,
  app_config: config(),
  is_public: false,
  ...over,
});

const renderPage = () =>
  renderWithProviders(
    <Routes>
      <Route path="/apps/:id" element={<OrchestrationPage />} />
    </Routes>,
    { route: "/apps/7" },
  );

beforeEach(() => {
  vi.clearAllMocks();
  mockGet.mockResolvedValue(detail());
  mockUpdate.mockResolvedValue(config());
  mockPublish.mockResolvedValue(detail({ status: "published" }));
});

describe("OrchestrationPage", () => {
  it("加载后渲染应用名", async () => {
    renderPage();
    expect(await screen.findByText("客服助手")).toBeInTheDocument();
  });

  it("改配置后自动保存（防抖）→ 调 updateDraftConfig", async () => {
    renderPage();
    await screen.findByText("客服助手");
    fireEvent.click(screen.getByRole("button", { name: "改一处配置" }));
    // 无手动「保存草稿」按钮：改动 600ms 后自动落库。
    await waitFor(
      () =>
        expect(mockUpdate).toHaveBeenCalledWith(7, expect.objectContaining({ dialog_round: 4 })),
      { timeout: 2000 },
    );
  });

  it("发布前先冲刷未落库改动，再调 publishApp", async () => {
    renderPage();
    await screen.findByText("客服助手");
    fireEvent.click(screen.getByRole("button", { name: "改一处配置" }));
    // 防抖还没触发就点发布：应先 flush 保存最新草稿，再发布。
    fireEvent.click(screen.getByRole("button", { name: "发布" }));
    await waitFor(() =>
      expect(mockUpdate).toHaveBeenCalledWith(7, expect.objectContaining({ dialog_round: 4 })),
    );
    await waitFor(() => expect(mockPublish).toHaveBeenCalled());
  });

  it("点发布 → 调 publishApp", async () => {
    renderPage();
    await screen.findByText("客服助手");
    fireEvent.click(screen.getByRole("button", { name: "发布" }));
    await waitFor(() => expect(mockPublish).toHaveBeenCalled());
  });
});
