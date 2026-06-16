import { fireEvent, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/api/plugins", () => ({ validateOpenapiSchema: vi.fn() }));

import { validateOpenapiSchema } from "@/api/plugins";
import { ApiError } from "@/lib/http/errors";
import { renderWithProviders } from "@/test/render";

import { OpenApiSchemaEditor } from "./OpenApiSchemaEditor";

const mockValidate = vi.mocked(validateOpenapiSchema);

const VALID_SCHEMA = JSON.stringify({
  server: "https://api.example.com",
  description: "demo",
  paths: { "/weather": { get: { operationId: "get_weather", description: "查天气", parameters: [] } } },
});

beforeEach(() => vi.clearAllMocks());

describe("OpenApiSchemaEditor", () => {
  it("校验通过 → 展示成功并解析出工具预览", async () => {
    mockValidate.mockResolvedValue(undefined);
    renderWithProviders(<OpenApiSchemaEditor value={VALID_SCHEMA} onChange={() => {}} />);

    fireEvent.click(screen.getByRole("button", { name: /校验 schema/ }));

    expect(await screen.findByText("校验通过")).toBeInTheDocument();
    expect(screen.getByText("get_weather")).toBeInTheDocument();
  });

  it("校验失败（422）→ 展示后端错误文案", async () => {
    mockValidate.mockRejectedValue(new ApiError(422, "operationId 重复"));
    renderWithProviders(<OpenApiSchemaEditor value={VALID_SCHEMA} onChange={() => {}} />);

    fireEvent.click(screen.getByRole("button", { name: /校验 schema/ }));

    expect(await screen.findByRole("alert")).toHaveTextContent("operationId 重复");
  });
});
