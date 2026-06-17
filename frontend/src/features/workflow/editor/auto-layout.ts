/** 依赖-free 的分层布局：按到开始节点的最长路径分列，列内纵向堆叠。 */
import type { WorkflowNode } from "@/types/workflows";

type MiniEdge = { source: string; target: string };

const COL_W = 280;
const ROW_H = 130;

export function layeredLayout(
  nodes: WorkflowNode[],
  edges: MiniEdge[],
): Record<string, { x: number; y: number }> {
  const ids = nodes.map((n) => n.id);
  const inDeg = new Map<string, number>(ids.map((id) => [id, 0]));
  const adj = new Map<string, string[]>();
  for (const e of edges) {
    if (!inDeg.has(e.source) || !inDeg.has(e.target)) continue;
    inDeg.set(e.target, (inDeg.get(e.target) ?? 0) + 1);
    if (!adj.has(e.source)) adj.set(e.source, []);
    adj.get(e.source)!.push(e.target);
  }

  // Kahn 拓扑 + 列号 = 前驱最大列 + 1
  const depth = new Map<string, number>(ids.map((id) => [id, 0]));
  const deg = new Map(inDeg);
  const queue = ids.filter((id) => (deg.get(id) ?? 0) === 0);
  while (queue.length) {
    const cur = queue.shift()!;
    for (const nxt of adj.get(cur) ?? []) {
      depth.set(nxt, Math.max(depth.get(nxt) ?? 0, (depth.get(cur) ?? 0) + 1));
      deg.set(nxt, (deg.get(nxt) ?? 0) - 1);
      if (deg.get(nxt) === 0) queue.push(nxt);
    }
  }

  const byCol = new Map<number, string[]>();
  for (const id of ids) {
    const c = depth.get(id) ?? 0;
    if (!byCol.has(c)) byCol.set(c, []);
    byCol.get(c)!.push(id);
  }

  const pos: Record<string, { x: number; y: number }> = {};
  for (const [col, colIds] of byCol) {
    colIds.forEach((id, row) => {
      pos[id] = { x: 60 + col * COL_W, y: 60 + row * ROW_H };
    });
  }
  return pos;
}
