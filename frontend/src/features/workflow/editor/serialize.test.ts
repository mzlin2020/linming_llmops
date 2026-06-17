import { describe, expect, it } from "vitest";

import type { DraftGraph } from "@/types/workflows";
import { EDGE_TYPE, toDraft, toFlow } from "./serialize";

const graph: DraftGraph = {
  nodes: [
    { id: "s", node_type: "start", title: "开始", description: "", position: { x: 1.4, y: 2.6 }, inputs: [] },
    { id: "t", node_type: "template_transform", title: "模板", description: "", position: { x: 200, y: 100 }, template: "x", inputs: [], outputs: [] },
    { id: "e", node_type: "end", title: "结束", description: "", position: { x: 400, y: 200 }, outputs: [] },
  ],
  edges: [
    { id: "e1", source: "s", source_type: "start", target: "t", target_type: "template_transform" },
    { id: "e2", source: "t", source_type: "template_transform", target: "e", target_type: "end" },
  ],
};

describe("toFlow", () => {
  it("把后端节点映射成 ReactFlow 节点（type=node_type，配置存 data.wf，start 不可删）", () => {
    const { nodes, edges } = toFlow(graph);
    const start = nodes.find((n) => n.id === "s")!;
    expect(start.type).toBe("start");
    expect(start.data.wf.node_type).toBe("start");
    expect(start.deletable).toBe(false);
    expect(nodes.find((n) => n.id === "t")!.deletable).toBe(true);
    expect(edges).toHaveLength(2);
    expect(edges[0].type).toBe(EDGE_TYPE);
  });
});

describe("toDraft", () => {
  it("回写后端图：位置取整，边的 source_type/target_type 按当前节点重算", () => {
    const flow = toFlow(graph);
    const draft = toDraft(flow.nodes, flow.edges);
    const start = draft.nodes.find((n) => n.id === "s")!;
    expect(start.position).toEqual({ x: 1, y: 3 }); // 1.4→1, 2.6→3
    const edge = draft.edges.find((e) => e.id === "e1")!;
    expect(edge.source_type).toBe("start");
    expect(edge.target_type).toBe("template_transform");
  });

  it("丢弃指向不存在节点的边", () => {
    const flow = toFlow(graph);
    const withDangling = [...flow.edges, { id: "x", source: "s", target: "ghost", type: EDGE_TYPE }];
    const draft = toDraft(flow.nodes, withDangling);
    expect(draft.edges.find((e) => e.id === "x")).toBeUndefined();
    expect(draft.edges).toHaveLength(2);
  });

  it("round-trip 保持节点/边数量稳定", () => {
    const flow = toFlow(graph);
    const draft = toDraft(flow.nodes, flow.edges);
    expect(draft.nodes).toHaveLength(3);
    expect(draft.edges).toHaveLength(2);
  });
});
