import { describe, expect, it } from "vitest";

import {
  extractImageUrls,
  historyToMessages,
  initialState,
  reducer,
  type ChatMessage,
  type ChatState,
  type HistoryRound,
} from "./chat-core";

describe("historyToMessages 附件映射", () => {
  it("把轮的 image_urls/file_infos 映射到 user 气泡（assistant 不带）", () => {
    const rounds: HistoryRound[] = [
      {
        id: 1,
        query: "看图",
        answer: "好的",
        status: "normal",
        error: "",
        image_urls: ["https://x.local/a.png"],
        file_infos: [{ url: "https://x.local/d.pdf", name: "d.pdf" }],
      },
    ];
    const [user, assistant] = historyToMessages(rounds);
    expect(user.role).toBe("user");
    expect(user.imageUrls).toEqual(["https://x.local/a.png"]);
    expect(user.fileInfos?.[0].name).toBe("d.pdf");
    expect(assistant.imageUrls).toBeUndefined();
  });

  it("无附件字段时回退空数组", () => {
    const [user] = historyToMessages([
      { id: 2, query: "q", answer: "a", status: "normal", error: "" },
    ]);
    expect(user.imageUrls).toEqual([]);
    expect(user.fileInfos).toEqual([]);
  });
});

describe("extractImageUrls 从工具 observation 抽取图片", () => {
  it("抽出 markdown 图片语法里的 URL", () => {
    expect(extractImageUrls("已生成图片：\n\n![一只猫](/api/images/file/abc.png)")).toEqual([
      "/api/images/file/abc.png",
    ]);
  });

  it("抽出多张图片", () => {
    const obs = "![a](/api/images/file/a.png) 和 ![b](https://x.local/b.jpg)";
    expect(extractImageUrls(obs)).toEqual(["/api/images/file/a.png", "https://x.local/b.jpg"]);
  });

  it("普通文本 / 非图片链接不被抽取", () => {
    expect(extractImageUrls("生成失败，请稍后再试")).toEqual([]);
    // 不带感叹号的是普通链接，非图片
    expect(extractImageUrls("详见 [文档](https://x.local/doc)")).toEqual([]);
  });

  it("空/无效输入回退空数组", () => {
    expect(extractImageUrls("")).toEqual([]);
  });
});

describe("reducer ADD_GENERATED_IMAGES 把工具图片挂到助手气泡", () => {
  const streaming = (): ChatState => ({
    messages: [
      { key: "u", role: "user", content: "画只猫", status: "done" },
      { key: "a", role: "assistant", content: "", status: "sending" },
    ],
  });

  it("把 URL 追加到末条助手的 generatedImages", () => {
    const next = reducer(streaming(), { type: "ADD_GENERATED_IMAGES", urls: ["/api/images/file/x.png"] });
    const last = next.messages[next.messages.length - 1];
    expect(last.generatedImages).toEqual(["/api/images/file/x.png"]);
  });

  it("去重：同一 URL 不重复追加", () => {
    let state = streaming();
    state = reducer(state, { type: "ADD_GENERATED_IMAGES", urls: ["/api/images/file/x.png"] });
    state = reducer(state, { type: "ADD_GENERATED_IMAGES", urls: ["/api/images/file/x.png", "/api/images/file/y.png"] });
    const last = state.messages[state.messages.length - 1];
    expect(last.generatedImages).toEqual(["/api/images/file/x.png", "/api/images/file/y.png"]);
  });

  it("末条助手已终态时不改动（late 帧守卫）", () => {
    const done: ChatState = {
      messages: [{ key: "a", role: "assistant", content: "好的", status: "done" } as ChatMessage],
    };
    const next = reducer(done, { type: "ADD_GENERATED_IMAGES", urls: ["/api/images/file/x.png"] });
    expect(next.messages[0].generatedImages).toBeUndefined();
  });

  it("初始空态下安全返回", () => {
    expect(reducer(initialState, { type: "ADD_GENERATED_IMAGES", urls: ["/x.png"] })).toEqual(initialState);
  });
});
