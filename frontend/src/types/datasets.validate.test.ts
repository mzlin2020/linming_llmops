import { describe, expect, it } from "vitest";

import { DEFAULT_PROCESS_RULE, validateProcessRule, type ProcessRule } from "./datasets";

const ruleWith = (segment: Partial<ProcessRule["segment"]>): ProcessRule => ({
  ...DEFAULT_PROCESS_RULE,
  segment: { ...DEFAULT_PROCESS_RULE.segment, ...segment },
});

describe("validateProcessRule", () => {
  it("默认规则通过（返回 null）", () => {
    expect(validateProcessRule(DEFAULT_PROCESS_RULE)).toBeNull();
  });

  it("分段长度 < 1 → 报错", () => {
    expect(validateProcessRule(ruleWith({ chunk_size: 0 }))).toMatch(/分段最大长度/);
  });

  it("重叠 ≥ 分段长度 → 报错", () => {
    expect(validateProcessRule(ruleWith({ chunk_size: 100, chunk_overlap: 100 }))).toMatch(
      /分段重叠长度/,
    );
    expect(validateProcessRule(ruleWith({ chunk_overlap: -1 }))).toMatch(/分段重叠长度/);
  });

  it("无非空分隔符 → 报错", () => {
    expect(validateProcessRule(ruleWith({ separators: ["", ""] }))).toMatch(/分隔符/);
  });
});
