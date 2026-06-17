import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/http/client", () => ({
  get: vi.fn(() => Promise.resolve({})),
  post: vi.fn(() => Promise.resolve({})),
}));

import { get, post } from "@/lib/http/client";
import { imageSrc, imageToImage, listImages, textToImage } from "./images";

describe("images api — 请求形状逐字对齐后端", () => {
  beforeEach(() => vi.clearAllMocks());

  it("textToImage → POST /images/text-to-image", () => {
    textToImage({ prompt: "一只猫", size: "1024x1024" });
    expect(post).toHaveBeenCalledWith("/images/text-to-image", { prompt: "一只猫", size: "1024x1024" });
  });

  it("imageToImage → POST /images/image-to-image（带 image_url）", () => {
    imageToImage({ prompt: "改水彩", image_url: "https://ok.local/x.png" });
    expect(post).toHaveBeenCalledWith("/images/image-to-image", {
      prompt: "改水彩",
      image_url: "https://ok.local/x.png",
    });
  });

  it("listImages → GET /images（分页参数）", () => {
    listImages({ current_page: 2, page_size: 12 });
    expect(get).toHaveBeenCalledWith("/images", { params: { current_page: 2, page_size: 12 } });
  });
});

describe("imageSrc", () => {
  it("默认 /api 基址下原样返回能力 URL（已含 /api 前缀）", () => {
    expect(imageSrc("/api/images/file/abc.png")).toBe("/api/images/file/abc.png");
  });

  it("绝对 URL 原样透传", () => {
    expect(imageSrc("https://cdn.example/x.png")).toBe("https://cdn.example/x.png");
  });
});
