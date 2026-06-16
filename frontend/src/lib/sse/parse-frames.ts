/** 解析出的 SSE 帧：事件名 + 已 JSON.parse 的 data（解析失败则保留原始字符串）。 */
export interface SseFrame {
  event: string;
  data: unknown;
}

/**
 * 把一个完整帧块（不含分隔的 `\n\n`）解析为 SseFrame。
 * 帧内逐行：`event:` → 事件名，`data:` → 数据行（可多行，按 `\n` 拼接）。
 * 无 data 行的块（纯注释/空块）返回 null。
 */
function parseBlock(block: string): SseFrame | null {
  let event = "message";
  const dataLines: string[] = [];

  for (const rawLine of block.split("\n")) {
    const line = rawLine.endsWith("\r") ? rawLine.slice(0, -1) : rawLine;
    if (line === "" || line.startsWith(":")) continue; // 空行 / 注释
    const idx = line.indexOf(":");
    const field = idx === -1 ? line : line.slice(0, idx);
    let value = idx === -1 ? "" : line.slice(idx + 1);
    if (value.startsWith(" ")) value = value.slice(1); // SSE 约定：冒号后单个空格忽略
    if (field === "event") event = value;
    else if (field === "data") dataLines.push(value);
  }

  if (dataLines.length === 0) return null;
  const raw = dataLines.join("\n");
  let data: unknown = raw;
  try {
    data = JSON.parse(raw);
  } catch {
    /* 非 JSON：保留原始字符串，容错不抛 */
  }
  return { event, data };
}

/**
 * 增量帧解析器（纯函数、无 fetch/DOM 依赖，便于脚本化字节流单测）。
 * `push(chunk)` 累积文本、按 `\n\n` 切出完整帧，**不完整的残帧留在缓冲**（跨 chunk 拆帧）。
 * `flush()` 在流结束时把缓冲里残留的最后一帧吐出（若有）。
 *
 * 后端帧格式为 `event: <name>\ndata: <JSON>\n\n`（见 backend/internal/service/_chat_common.py）。
 */
export function createFrameParser() {
  let buffer = "";

  return {
    push(chunk: string): SseFrame[] {
      // 归一 CRLF→LF（缓冲只存残帧，体量很小），保证 `\n\n` 分隔与跨 chunk CRLF 都成立。
      buffer = (buffer + chunk).replace(/\r\n/g, "\n");
      const frames: SseFrame[] = [];
      let sep: number;
      while ((sep = buffer.indexOf("\n\n")) !== -1) {
        const block = buffer.slice(0, sep);
        buffer = buffer.slice(sep + 2);
        const frame = parseBlock(block);
        if (frame) frames.push(frame);
      }
      return frames;
    },
    flush(): SseFrame[] {
      const block = buffer;
      buffer = "";
      if (block.trim() === "") return [];
      const frame = parseBlock(block);
      return frame ? [frame] : [];
    },
  };
}
