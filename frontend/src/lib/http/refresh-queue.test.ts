import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("./refresh-api", () => ({ rawRefresh: vi.fn() }));

import { useAuthStore } from "@/stores/auth-store";
import { rawRefresh } from "./refresh-api";
import { ensureFreshToken, onAuthFailure } from "./refresh-queue";

const mockedRawRefresh = vi.mocked(rawRefresh);

beforeEach(() => {
  useAuthStore.getState().clear();
  useAuthStore.setState({ refreshToken: "rt-1" });
  mockedRawRefresh.mockReset();
});

describe("ensureFreshToken 单飞刷新", () => {
  it("并发 401 只发起一次刷新，所有调用拿到同一新 token，并写回 store", async () => {
    let resolveRefresh!: (t: string) => void;
    mockedRawRefresh.mockReturnValue(
      new Promise<string>((res) => {
        resolveRefresh = res;
      }),
    );

    const p1 = ensureFreshToken();
    const p2 = ensureFreshToken();
    const p3 = ensureFreshToken();
    resolveRefresh("new-access");

    const tokens = await Promise.all([p1, p2, p3]);
    expect(tokens).toEqual(["new-access", "new-access", "new-access"]);
    expect(mockedRawRefresh).toHaveBeenCalledTimes(1);
    expect(useAuthStore.getState().accessToken).toBe("new-access");
  });

  it("刷新失败时拒绝全部排队请求", async () => {
    let rejectRefresh!: (e: unknown) => void;
    mockedRawRefresh.mockReturnValue(
      new Promise<string>((_, rej) => {
        rejectRefresh = rej;
      }),
    );

    const p1 = ensureFreshToken();
    const p2 = ensureFreshToken();
    rejectRefresh(new Error("refresh expired"));

    await expect(p1).rejects.toThrow();
    await expect(p2).rejects.toThrow();
    expect(mockedRawRefresh).toHaveBeenCalledTimes(1);
  });

  it("无 refresh_token 时直接抛错，不发起刷新", async () => {
    useAuthStore.getState().clear();
    await expect(ensureFreshToken()).rejects.toThrow();
    expect(mockedRawRefresh).not.toHaveBeenCalled();
  });
});

describe("onAuthFailure", () => {
  it("清空会话", () => {
    // 预置到 /login，命中跳转守卫的短路分支，避免 jsdom 真实导航。
    window.history.pushState({}, "", "/login");
    useAuthStore.setState({ accessToken: "a", refreshToken: "r" });
    onAuthFailure();
    expect(useAuthStore.getState().accessToken).toBeNull();
    expect(useAuthStore.getState().refreshToken).toBeNull();
  });
});
