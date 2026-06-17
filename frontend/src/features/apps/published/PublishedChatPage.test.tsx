import { screen } from "@testing-library/react";
import { Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/api/apps", () => ({ getApp: vi.fn(), getPublishedConfig: vi.fn() }));

import { getApp, getPublishedConfig } from "@/api/apps";
import { renderWithProviders } from "@/test/render";
import type { AppDetail } from "@/types/apps";

import { PublishedChatPage } from "./PublishedChatPage";

beforeEach(() => {
  vi.clearAllMocks();
});

describe("PublishedChatPage 未发布门控", () => {
  it("应用未发布时提示去发布、不挂载对话", async () => {
    vi.mocked(getApp).mockResolvedValue({
      id: 5,
      name: "测试应用",
      status: "draft",
    } as unknown as AppDetail);
    vi.mocked(getPublishedConfig).mockResolvedValue(null);

    renderWithProviders(
      <Routes>
        <Route path="/apps/:id/chat" element={<PublishedChatPage />} />
      </Routes>,
      { route: "/apps/5/chat" },
    );

    expect(await screen.findByText(/尚未发布/)).toBeInTheDocument();
    expect(screen.getByText("去编排并发布")).toBeInTheDocument();
  });
});
