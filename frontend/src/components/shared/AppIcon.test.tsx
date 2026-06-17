import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { AppIcon, pickDefaultIcon } from "./AppIcon";

describe("AppIcon", () => {
  it("空图标 → 渲染 lucide 占位（svg），不出 img（避免裂图）", () => {
    const { container } = render(<AppIcon icon="" name="客服助手" />);
    expect(container.querySelector("img")).toBeNull();
    expect(container.querySelector("svg")).not.toBeNull();
  });

  it("后端默认占位路径 /app-icons/*.png → 仍回退占位，不出 img", () => {
    const { container } = render(<AppIcon icon="/app-icons/cube.png" name="x" />);
    expect(container.querySelector("img")).toBeNull();
    expect(container.querySelector("svg")).not.toBeNull();
  });

  it("真实绝对 URL → 渲染 img", () => {
    const { container } = render(<AppIcon icon="https://cdn.example.com/a.png" name="x" />);
    const img = container.querySelector("img");
    expect(img).not.toBeNull();
    expect(img?.getAttribute("src")).toBe("https://cdn.example.com/a.png");
  });

  it("占位图标按名称稳定（同名同图，异名大概率不同）", () => {
    expect(pickDefaultIcon("客服助手")).toBe(pickDefaultIcon("客服助手"));
    // 不同名字命中不同图标（同一组件引用相等性比较）
    const names = ["a", "b", "c", "d", "e", "f", "g", "h"];
    const distinct = new Set(names.map((n) => pickDefaultIcon(n)));
    expect(distinct.size).toBeGreaterThan(1);
  });
});
