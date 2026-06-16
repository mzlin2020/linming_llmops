import { fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/api/account", () => ({ getMe: vi.fn() }));
vi.mock("@/api/auth", () => ({ logout: vi.fn() }));

import { getMe } from "@/api/account";
import { logout } from "@/api/auth";
import { renderWithProviders } from "@/test/render";

import { AccountView } from "./AccountView";

const mockMe = vi.mocked(getMe);
const mockLogout = vi.mocked(logout);

beforeEach(() => {
  vi.clearAllMocks();
  mockMe.mockResolvedValue({ id: 7, email: "u@example.com", name: "小明", avatar: null });
  mockLogout.mockResolvedValue({} as never);
});

describe("AccountView", () => {
  it("渲染账户资料", async () => {
    renderWithProviders(<AccountView />);
    expect(await screen.findByText("小明")).toBeInTheDocument();
    expect(screen.getByText("u@example.com")).toBeInTheDocument();
  });

  it("点退出 → 调 logout", async () => {
    renderWithProviders(<AccountView />);
    await screen.findByText("小明");
    fireEvent.click(screen.getByRole("button", { name: /退出登录/ }));
    await waitFor(() => expect(mockLogout).toHaveBeenCalled());
  });
});
