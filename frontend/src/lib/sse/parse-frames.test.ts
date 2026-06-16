import { describe, expect, it } from "vitest";

import { createFrameParser } from "./parse-frames";

describe("createFrameParser", () => {
  it("解析单个完整帧", () => {
    const p = createFrameParser();
    const frames = p.push('event: message\ndata: {"delta":"hi"}\n\n');
    expect(frames).toEqual([{ event: "message", data: { delta: "hi" } }]);
  });

  it("跨 chunk 拆帧：残帧留缓冲，补齐后吐出", () => {
    const p = createFrameParser();
    expect(p.push("event: mess")).toEqual([]); // 还没凑齐
    const frames = p.push('age\ndata: {"delta":"yo"}\n\n');
    expect(frames).toEqual([{ event: "message", data: { delta: "yo" } }]);
  });

  it("一次 chunk 含多帧", () => {
    const p = createFrameParser();
    const frames = p.push(
      'event: ping\ndata: {"task_id":"t1"}\n\n' +
        'event: message\ndata: {"delta":"a"}\n\n',
    );
    expect(frames).toHaveLength(2);
    expect(frames[0].event).toBe("ping");
    expect(frames[1]).toEqual({ event: "message", data: { delta: "a" } });
  });

  it("解析 error 帧", () => {
    const p = createFrameParser();
    const frames = p.push('event: error\ndata: {"message":"boom","message_id":3}\n\n');
    expect(frames[0]).toEqual({
      event: "error",
      data: { message: "boom", message_id: 3 },
    });
  });

  it("data 非 JSON 时保留原始字符串，不抛", () => {
    const p = createFrameParser();
    const frames = p.push("event: message\ndata: not-json\n\n");
    expect(frames[0]).toEqual({ event: "message", data: "not-json" });
  });

  it("忽略注释行与空块", () => {
    const p = createFrameParser();
    const frames = p.push(": this is a comment\n\n" + 'event: ping\ndata: {}\n\n');
    expect(frames).toEqual([{ event: "ping", data: {} }]);
  });

  it("缺省事件名为 message", () => {
    const p = createFrameParser();
    const frames = p.push('data: {"delta":"x"}\n\n');
    expect(frames[0].event).toBe("message");
  });

  it("flush 吐出末尾无 \\n\\n 收尾的残帧", () => {
    const p = createFrameParser();
    expect(p.push('event: agent_end\ndata: {"status":"normal"}')).toEqual([]);
    const tail = p.flush();
    expect(tail).toEqual([{ event: "agent_end", data: { status: "normal" } }]);
  });

  it("容忍 CRLF 行尾", () => {
    const p = createFrameParser();
    const frames = p.push('event: message\r\ndata: {"delta":"r"}\r\n\r\n');
    expect(frames[0]).toEqual({ event: "message", data: { delta: "r" } });
  });
});
