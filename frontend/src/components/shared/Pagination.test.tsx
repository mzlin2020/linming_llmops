import { fireEvent, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { renderWithProviders } from "@/test/render";
import type { Paginator } from "@/types/api";

import { Pagination } from "./Pagination";

const paginator = (over: Partial<Paginator> = {}): Paginator => ({
  current_page: 1,
  page_size: 12,
  total_page: 3,
  total_record: 30,
  ...over,
});

describe("Pagination", () => {
  it("单页时不渲染", () => {
    const { container } = renderWithProviders(
      <Pagination paginator={paginator({ total_page: 1 })} onChange={() => {}} />,
    );
    expect(container).toBeEmptyDOMElement();
  });

  it("首页禁用上一页、点下一页回调下一页码", () => {
    const onChange = vi.fn();
    renderWithProviders(<Pagination paginator={paginator()} onChange={onChange} />);
    expect(screen.getByLabelText("上一页")).toBeDisabled();
    fireEvent.click(screen.getByLabelText("下一页"));
    expect(onChange).toHaveBeenCalledWith(2);
  });

  it("末页禁用下一页", () => {
    renderWithProviders(<Pagination paginator={paginator({ current_page: 3 })} onChange={() => {}} />);
    expect(screen.getByLabelText("下一页")).toBeDisabled();
  });
});
