import { render, screen } from "@testing-library/react";
import App from "./App";

// Phase 0 冒烟测试：仅验证测试框架与渲染链路可用。
describe("App", () => {
  it("renders the app heading", () => {
    render(<App />);
    expect(
      screen.getByRole("heading", { name: /linming_llmops/i }),
    ).toBeInTheDocument();
  });
});
