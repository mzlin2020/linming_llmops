import { fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/api/auth", () => ({ login: vi.fn(), register: vi.fn(), logout: vi.fn() }));

import { login } from "@/api/auth";
import { ApiError } from "@/lib/http/errors";
import { useAuthStore } from "@/stores/auth-store";
import { renderWithProviders } from "@/test/render";
import { LoginPage } from "./LoginPage";

const mockedLogin = vi.mocked(login);

beforeEach(() => {
  useAuthStore.getState().clear();
  mockedLogin.mockReset();
});

describe("LoginPage", () => {
  it("邮箱格式非法 → 显示校验错误且不提交", async () => {
    renderWithProviders(<LoginPage />, { route: "/login" });
    fireEvent.change(screen.getByLabelText("邮箱"), { target: { value: "bad" } });
    fireEvent.change(screen.getByLabelText("密码"), { target: { value: "x" } });
    fireEvent.click(screen.getByRole("button", { name: "登录" }));

    expect(await screen.findByText("请输入有效邮箱")).toBeInTheDocument();
    expect(mockedLogin).not.toHaveBeenCalled();
  });

  it("登录成功 → 调 api 并写入会话", async () => {
    mockedLogin.mockResolvedValue({
      access_token: "at",
      refresh_token: "rt",
      account: { id: 1, email: "a@b.com", name: "A", avatar: null },
    });
    renderWithProviders(<LoginPage />, { route: "/login" });
    fireEvent.change(screen.getByLabelText("邮箱"), { target: { value: "a@b.com" } });
    fireEvent.change(screen.getByLabelText("密码"), { target: { value: "secret" } });
    fireEvent.click(screen.getByRole("button", { name: "登录" }));

    await waitFor(() => expect(useAuthStore.getState().accessToken).toBe("at"));
    expect(mockedLogin).toHaveBeenCalledWith("a@b.com", "secret");
    expect(useAuthStore.getState().account?.email).toBe("a@b.com");
  });

  it("登录失败 → 显示后端错误信息", async () => {
    mockedLogin.mockRejectedValue(new ApiError(401, "邮箱或密码错误"));
    renderWithProviders(<LoginPage />, { route: "/login" });
    fireEvent.change(screen.getByLabelText("邮箱"), { target: { value: "a@b.com" } });
    fireEvent.change(screen.getByLabelText("密码"), { target: { value: "secret" } });
    fireEvent.click(screen.getByRole("button", { name: "登录" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("邮箱或密码错误");
    expect(useAuthStore.getState().accessToken).toBeNull();
  });
});
