import { describe, expect, it } from "vitest";

import type { VariableEntity, WorkflowNode } from "@/types/workflows";
import { getPredecessors, validateGraph, wouldCreateCycle } from "./validation";

const node = (id: string, node_type: WorkflowNode["node_type"], extra: Partial<WorkflowNode> = {}): WorkflowNode => ({
  id,
  node_type,
  title: id,
  description: "",
  position: { x: 0, y: 0 },
  ...extra,
});

const refVar = (name: string, refNode: string, refVar: string): VariableEntity => ({
  name,
  description: "",
  required: true,
  type: "string",
  value: { type: "ref", content: { ref_node_id: refNode, ref_var_name: refVar } },
  meta: {},
});

describe("validateGraph", () => {
  it("最简合法图（start→end，无引用）通过", () => {
    const nodes = [node("s", "start", { inputs: [] }), node("e", "end", { outputs: [] })];
    const edges = [{ source: "s", target: "e" }];
    expect(validateGraph(nodes, edges)).toEqual([]);
  });

  it("缺结束节点报错", () => {
    const errs = validateGraph([node("s", "start")], []);
    expect(errs.some((m) => m.includes("结束节点"))).toBe(true);
  });

  it("两个开始节点报错", () => {
    const nodes = [node("s1", "start"), node("s2", "start"), node("e", "end")];
    expect(validateGraph(nodes, [{ source: "s1", target: "e" }]).some((m) => m.includes("开始节点"))).toBe(true);
  });

  it("环路报错", () => {
    const nodes = [node("s", "start"), node("a", "llm"), node("b", "llm"), node("e", "end")];
    const edges = [
      { source: "s", target: "a" },
      { source: "a", target: "b" },
      { source: "b", target: "a" },
    ];
    expect(validateGraph(nodes, edges).some((m) => m.includes("环路"))).toBe(true);
  });

  it("孤立节点报错", () => {
    const nodes = [node("s", "start"), node("e", "end"), node("x", "llm")];
    expect(validateGraph(nodes, [{ source: "s", target: "e" }]).some((m) => m.includes("孤立"))).toBe(true);
  });

  it("无效变量引用报错", () => {
    const nodes = [
      node("s", "start", { inputs: [] }),
      node("e", "end", { outputs: [refVar("out", "ghost", "x")] }),
    ];
    expect(validateGraph(nodes, [{ source: "s", target: "e" }]).some((m) => m.includes("无效"))).toBe(true);
  });
});

describe("wouldCreateCycle", () => {
  const edges = [
    { source: "a", target: "b" },
    { source: "b", target: "c" },
  ];
  it("回边成环", () => expect(wouldCreateCycle(edges, "c", "a")).toBe(true));
  it("自环", () => expect(wouldCreateCycle(edges, "a", "a")).toBe(true));
  it("不成环的新边", () => expect(wouldCreateCycle(edges, "a", "z")).toBe(false));
});

describe("getPredecessors", () => {
  it("沿入边回溯全部前驱", () => {
    const nodes = [node("a", "start"), node("b", "llm"), node("c", "end")];
    const edges = [
      { source: "a", target: "b" },
      { source: "b", target: "c" },
    ];
    const preds = getPredecessors("c", nodes, edges).map((n) => n.id).sort();
    expect(preds).toEqual(["a", "b"]);
  });
});
