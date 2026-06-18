import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { ChatMessage } from "./chat-core";
import { MessageItem } from "./MessageItem";

describe("MessageItem 用户附件", () => {
  it("渲染图片缩略图与文档 chip（连同文本）", () => {
    const msg: ChatMessage = {
      key: "u-1",
      role: "user",
      content: "看这张图",
      status: "done",
      imageUrls: ["https://x.local/a.png"],
      fileInfos: [{ url: "https://x.local/doc.pdf", name: "报告.pdf", extension: "pdf" }],
    };
    render(<MessageItem message={msg} />);
    const img = screen.getByAltText("附件图片") as HTMLImageElement;
    expect(img.src).toContain("a.png");
    expect(screen.getByText("报告.pdf")).toBeInTheDocument();
    expect(screen.getByText("看这张图")).toBeInTheDocument();
  });

  it("无附件时不渲染附件区", () => {
    const msg: ChatMessage = { key: "u-2", role: "user", content: "纯文本", status: "done" };
    render(<MessageItem message={msg} />);
    expect(screen.queryByAltText("附件图片")).toBeNull();
    expect(screen.getByText("纯文本")).toBeInTheDocument();
  });
});

describe("MessageItem 助手生成图片", () => {
  it("渲染工具产出的生成图片", () => {
    const msg: ChatMessage = {
      key: "a-1",
      role: "assistant",
      content: "已为你生成图片",
      status: "done",
      generatedImages: ["/api/images/file/abc.png"],
    };
    render(<MessageItem message={msg} />);
    const img = screen.getByAltText("生成图片") as HTMLImageElement;
    expect(img.src).toContain("/api/images/file/abc.png");
  });

  it("URL 已出现在正文里时不重复渲染（避免模型复述导致双图）", () => {
    const msg: ChatMessage = {
      key: "a-2",
      role: "assistant",
      content: "![猫](/api/images/file/abc.png)",
      status: "done",
      generatedImages: ["/api/images/file/abc.png"],
    };
    render(<MessageItem message={msg} />);
    // 正文 markdown 已渲染该图，生成图片块不应再渲染同一 URL
    expect(screen.queryByAltText("生成图片")).toBeNull();
  });
});
