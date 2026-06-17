/**
 * 客户端图校验（调试/发布前的快速反馈，镜像后端 WorkflowConfig 严格校验）+ 图论助手。
 * 这是「友好提示」而非安全边界——真正的权威校验在后端。
 */
import { MAX_NODES, type VariableEntity, type WorkflowNode } from "@/types/workflows";

type MiniEdge = { source: string; target: string };

/** 节点暴露给下游引用的变量：start 节点是它的 inputs（工作流入参），其余是 outputs。 */
export function getRefSourceVars(node: WorkflowNode): VariableEntity[] {
  return node.node_type === "start" ? node.inputs ?? [] : node.outputs ?? [];
}

/** 某节点的全部前驱节点（BFS 沿入边回溯）。 */
export function getPredecessors(
  nodeId: string,
  nodes: WorkflowNode[],
  edges: MiniEdge[],
): WorkflowNode[] {
  const byId = new Map(nodes.map((n) => [n.id, n]));
  const incoming = new Map<string, string[]>();
  for (const e of edges) {
    if (!incoming.has(e.target)) incoming.set(e.target, []);
    incoming.get(e.target)!.push(e.source);
  }
  const seen = new Set<string>();
  const queue = [...(incoming.get(nodeId) ?? [])];
  while (queue.length) {
    const cur = queue.shift()!;
    if (seen.has(cur)) continue;
    seen.add(cur);
    for (const p of incoming.get(cur) ?? []) queue.push(p);
  }
  return [...seen].map((id) => byId.get(id)).filter((n): n is WorkflowNode => n != null);
}

/** 加一条 source→target 边是否会成环（在现有边基础上 DFS）。 */
export function wouldCreateCycle(edges: MiniEdge[], source: string, target: string): boolean {
  if (source === target) return true;
  const adj = new Map<string, string[]>();
  for (const e of edges) {
    if (!adj.has(e.source)) adj.set(e.source, []);
    adj.get(e.source)!.push(e.target);
  }
  // 从 target 出发若能回到 source，则新增 source→target 成环。
  const stack = [target];
  const seen = new Set<string>();
  while (stack.length) {
    const cur = stack.pop()!;
    if (cur === source) return true;
    if (seen.has(cur)) continue;
    seen.add(cur);
    for (const nxt of adj.get(cur) ?? []) stack.push(nxt);
  }
  return false;
}

/** 返回错误消息数组（空 = 校验通过）。 */
export function validateGraph(nodes: WorkflowNode[], edges: MiniEdge[]): string[] {
  const errors: string[] = [];
  if (nodes.length === 0) {
    errors.push("画布为空，请先添加节点");
    return errors;
  }
  if (nodes.length > MAX_NODES) errors.push(`节点数超过上限（最多 ${MAX_NODES} 个）`);

  const starts = nodes.filter((n) => n.node_type === "start");
  const ends = nodes.filter((n) => n.node_type === "end");
  if (starts.length !== 1) errors.push("必须有且只有一个开始节点");
  if (ends.length !== 1) errors.push("必须有且只有一个结束节点");

  const titles = nodes.map((n) => n.title.trim());
  if (new Set(titles).size !== titles.length) errors.push("存在重名节点，请保证标题唯一");

  const inDeg = new Map<string, number>();
  const outDeg = new Map<string, number>();
  for (const n of nodes) {
    inDeg.set(n.id, 0);
    outDeg.set(n.id, 0);
  }
  for (const e of edges) {
    outDeg.set(e.source, (outDeg.get(e.source) ?? 0) + 1);
    inDeg.set(e.target, (inDeg.get(e.target) ?? 0) + 1);
  }
  const start = starts[0];
  const end = ends[0];
  if (start && (inDeg.get(start.id) ?? 0) > 0) errors.push("开始节点不能有入边");
  if (end && (outDeg.get(end.id) ?? 0) > 0) errors.push("结束节点不能有出边");

  // 连通性：从开始节点 BFS 应覆盖全部节点
  if (start) {
    const adj = new Map<string, string[]>();
    for (const e of edges) {
      if (!adj.has(e.source)) adj.set(e.source, []);
      adj.get(e.source)!.push(e.target);
    }
    const reached = new Set<string>([start.id]);
    const queue = [start.id];
    while (queue.length) {
      const cur = queue.shift()!;
      for (const nxt of adj.get(cur) ?? []) {
        if (!reached.has(nxt)) {
          reached.add(nxt);
          queue.push(nxt);
        }
      }
    }
    if (reached.size !== nodes.length) errors.push("存在未连接到开始节点的孤立节点");
  }

  // 无环（Kahn 拓扑排序）
  if (!isAcyclic(nodes, edges)) errors.push("图中存在环路，工作流必须是有向无环图");

  // 变量引用有效性：ref 必须指向前驱节点的现有输出变量
  for (const n of nodes) {
    const preds = getPredecessors(n.id, nodes, edges);
    const predIds = new Set(preds.map((p) => p.id));
    for (const v of [...(n.inputs ?? []), ...(n.outputs ?? [])]) {
      if (v.value?.type !== "ref") continue;
      const ref = v.value.content;
      if (!ref.ref_node_id || !predIds.has(ref.ref_node_id)) {
        errors.push(`节点「${n.title}」的变量「${v.name}」引用了无效的上游节点`);
        continue;
      }
      const src = preds.find((p) => p.id === ref.ref_node_id)!;
      if (!getRefSourceVars(src).some((sv) => sv.name === ref.ref_var_name)) {
        errors.push(`节点「${n.title}」的变量「${v.name}」引用了不存在的上游变量`);
      }
    }
  }

  return [...new Set(errors)];
}

function isAcyclic(nodes: WorkflowNode[], edges: MiniEdge[]): boolean {
  const inDeg = new Map<string, number>(nodes.map((n) => [n.id, 0]));
  const adj = new Map<string, string[]>();
  for (const e of edges) {
    if (!inDeg.has(e.source) || !inDeg.has(e.target)) continue;
    inDeg.set(e.target, (inDeg.get(e.target) ?? 0) + 1);
    if (!adj.has(e.source)) adj.set(e.source, []);
    adj.get(e.source)!.push(e.target);
  }
  const queue = [...inDeg.entries()].filter(([, d]) => d === 0).map(([id]) => id);
  let visited = 0;
  while (queue.length) {
    const cur = queue.shift()!;
    visited++;
    for (const nxt of adj.get(cur) ?? []) {
      inDeg.set(nxt, (inDeg.get(nxt) ?? 0) - 1);
      if (inDeg.get(nxt) === 0) queue.push(nxt);
    }
  }
  return visited === nodes.length;
}
