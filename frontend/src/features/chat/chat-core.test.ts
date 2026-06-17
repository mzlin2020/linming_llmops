import { describe, expect, it } from "vitest";

import { historyToMessages, type HistoryRound } from "./chat-core";

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
