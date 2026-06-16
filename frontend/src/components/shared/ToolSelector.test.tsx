import { fireEvent, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/api/plugins", () => ({
  listBuiltinTools: vi.fn(),
  listApiTools: vi.fn(),
}));

import { listApiTools, listBuiltinTools } from "@/api/plugins";
import { renderWithProviders } from "@/test/render";
import type { ToolRef } from "@/types/plugins";

import { ToolSelector } from "./ToolSelector";

const mockBuiltin = vi.mocked(listBuiltinTools);
const mockApi = vi.mocked(listApiTools);

const BUILTIN = [
  {
    name: "google",
    label: "Google",
    description: "搜索",
    background: "",
    category: "search",
    created_at: 0,
    tools: [{ name: "google_search", label: "谷歌搜索", description: "web 搜索", inputs: [] }],
  },
];
const API_PAGE = {
  list: [
    {
      id: 5,
      name: "weather",
      icon: "",
      description: "天气",
      headers: [],
      tools: [{ id: 9, name: "get_weather", description: "查天气", inputs: [] }],
      is_public: false,
      created_at: 0,
    },
  ],
  paginator: { current_page: 1, page_size: 50, total_page: 1, total_record: 1 },
};

beforeEach(() => {
  vi.clearAllMocks();
  mockBuiltin.mockResolvedValue(BUILTIN);
  mockApi.mockResolvedValue(API_PAGE);
});

describe("ToolSelector", () => {
  it("勾选内置工具 → 发出 builtin_tool 规范引用", async () => {
    const onChange = vi.fn();
    renderWithProviders(<ToolSelector value={[]} onChange={onChange} />);
    fireEvent.click(await screen.findByRole("checkbox", { name: /谷歌搜索/ }));
    expect(onChange).toHaveBeenCalledWith([
      { type: "builtin_tool", provider: { name: "google" }, tool: { name: "google_search", params: {} } },
    ]);
  });

  it("勾选自定义工具 → 发出 api_tool 规范引用", async () => {
    const onChange = vi.fn();
    renderWithProviders(<ToolSelector value={[]} onChange={onChange} />);
    fireEvent.click(await screen.findByRole("checkbox", { name: /get_weather/ }));
    expect(onChange).toHaveBeenCalledWith([
      { type: "api_tool", provider: { id: 5, name: "weather" }, tool: { id: 9, name: "get_weather" } },
    ]);
  });

  it("已选项再点 → 取消（发出空数组）", async () => {
    const ref: ToolRef = {
      type: "builtin_tool",
      provider: { name: "google" },
      tool: { name: "google_search", params: {} },
    };
    const onChange = vi.fn();
    renderWithProviders(<ToolSelector value={[ref]} onChange={onChange} />);
    const checkbox = await screen.findByRole("checkbox", { name: /谷歌搜索/ });
    expect(checkbox).toBeChecked();
    fireEvent.click(checkbox);
    expect(onChange).toHaveBeenCalledWith([]);
  });

  it("达到 10 个上限后，未选项被禁用", async () => {
    const value: ToolRef[] = Array.from({ length: 10 }, (_, i) => ({
      type: "builtin_tool",
      provider: { name: `p${i}` },
      tool: { name: `t${i}`, params: {} },
    }));
    renderWithProviders(<ToolSelector value={value} onChange={() => {}} />);
    expect(await screen.findByRole("checkbox", { name: /get_weather/ })).toBeDisabled();
  });
});
