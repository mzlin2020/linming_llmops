import { create } from "zustand";
import { persist } from "zustand/middleware";

interface AiModelState {
  /** 用户为首页助手选定的模型 provider；null = 用「默认模型」。 */
  provider: string | null;
  /** 选定的模型名；与 provider 成对，null = 默认。 */
  model: string | null;
  /** 选定一个具体模型（provider 与 model 必须成对）。 */
  setModel: (provider: string, model: string) => void;
  /** 回到「默认模型」：清空覆盖，发送时由后端按 app/env 默认解析。 */
  clearModel: () => void;
}

/**
 * 首页助手的模型选择（持久化到 localStorage）。
 * 后端 `/assistant-agent/chat` 接受可选 provider/model 覆盖本轮模型；缺省（null）则服务端回退默认。
 * 读写不依赖 React 上下文——发送时在组件树外用 `useAiModelStore.getState()` 取值拼请求体。
 */
export const useAiModelStore = create<AiModelState>()(
  persist(
    (set) => ({
      provider: null,
      model: null,
      setModel: (provider, model) => set({ provider, model }),
      clearModel: () => set({ provider: null, model: null }),
    }),
    { name: "ai-model" },
  ),
);
