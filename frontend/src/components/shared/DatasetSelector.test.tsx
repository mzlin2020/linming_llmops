import { fireEvent, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/api/datasets", () => ({ listDatasets: vi.fn() }));

import { listDatasets } from "@/api/datasets";
import { renderWithProviders } from "@/test/render";

import { DatasetSelector } from "./DatasetSelector";

const mockList = vi.mocked(listDatasets);

const ds = (id: number) => ({
  id,
  name: `库${id}`,
  icon: "",
  description: "",
  document_count: 0,
  character_count: 0,
  hit_count: 0,
  created_at: 0,
  updated_at: 0,
});

const page = (ids: number[]) => ({
  list: ids.map(ds),
  paginator: { current_page: 1, page_size: 50, total_page: 1, total_record: ids.length },
});

beforeEach(() => {
  vi.clearAllMocks();
});

describe("DatasetSelector", () => {
  it("勾选发出 number[]", async () => {
    mockList.mockResolvedValue(page([1, 2, 3]));
    const onChange = vi.fn();
    renderWithProviders(<DatasetSelector value={[]} onChange={onChange} />);
    await screen.findByText("库1");
    fireEvent.click(screen.getAllByRole("checkbox")[0]);
    expect(onChange).toHaveBeenCalledWith([1]);
  });

  it("取消勾选移除 id", async () => {
    mockList.mockResolvedValue(page([1, 2, 3]));
    const onChange = vi.fn();
    renderWithProviders(<DatasetSelector value={[2]} onChange={onChange} />);
    await screen.findByText("库2");
    fireEvent.click(screen.getAllByRole("checkbox")[1]);
    expect(onChange).toHaveBeenCalledWith([]);
  });

  it("达到 5 上限时禁用未选项", async () => {
    mockList.mockResolvedValue(page([1, 2, 3, 4, 5, 6]));
    renderWithProviders(<DatasetSelector value={[1, 2, 3, 4, 5]} onChange={() => {}} />);
    await screen.findByText("库6");
    const boxes = screen.getAllByRole("checkbox");
    expect(boxes[5]).toBeDisabled(); // 库6 未选 → 禁用
    expect(boxes[0]).not.toBeDisabled(); // 库1 已选 → 可取消
  });
});
