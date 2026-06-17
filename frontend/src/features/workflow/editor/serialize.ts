/**
 * 后端图 ↔ ReactFlow 双向序列化。
 *
 * ReactFlow 只负责「位置 + 连线」；整个节点配置原样存在 `data.wf` 里随存随取。
 * 边的 source_type/target_type 在序列化回后端时按当前节点重算，保证与图同步。
 */
import type { Edge, Node } from "@xyflow/react";

import type { DraftGraph, NodeType, WorkflowEdge, WorkflowNode } from "@/types/workflows";

export type WfNodeData = { wf: WorkflowNode };
export type WfFlowNode = Node<WfNodeData>;

export const EDGE_TYPE = "deletable";

/** 后端 DraftGraph → ReactFlow 受控状态。 */
export function toFlow(graph: DraftGraph): { nodes: WfFlowNode[]; edges: Edge[] } {
  const nodes: WfFlowNode[] = (graph.nodes ?? []).map((n) => ({
    id: n.id,
    type: n.node_type,
    position: { x: n.position?.x ?? 0, y: n.position?.y ?? 0 },
    data: { wf: n },
    deletable: n.node_type !== "start",
  }));
  const edges: Edge[] = (graph.edges ?? []).map((e) => ({
    id: e.id,
    source: e.source,
    target: e.target,
    type: EDGE_TYPE,
  }));
  return { nodes, edges };
}

/** ReactFlow 受控状态 → 后端 DraftGraph（位置取整，边类型按当前节点重算）。 */
export function toDraft(nodes: WfFlowNode[], edges: Edge[]): DraftGraph {
  const typeById = new Map<string, NodeType>(nodes.map((n) => [n.id, n.data.wf.node_type]));
  const wfNodes: WorkflowNode[] = nodes.map((n) => ({
    ...n.data.wf,
    position: { x: Math.round(n.position.x), y: Math.round(n.position.y) },
  }));
  const wfEdges: WorkflowEdge[] = edges
    .filter((e) => typeById.has(e.source) && typeById.has(e.target))
    .map((e) => ({
      id: e.id,
      source: e.source,
      source_type: typeById.get(e.source)!,
      target: e.target,
      target_type: typeById.get(e.target)!,
    }));
  return { nodes: wfNodes, edges: wfEdges };
}
