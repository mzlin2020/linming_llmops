/**
 * 工作流编辑器状态（zustand 模块级单例；编辑页挂载时 init、卸载时 reset）。
 * 持图（ReactFlow nodes/edges）+ 选中 + 保存态 + 调试帧；草稿 600ms 防抖自动保存。
 */
import {
  addEdge,
  applyEdgeChanges,
  applyNodeChanges,
  type Connection,
  type Edge,
  type EdgeChange,
  type NodeChange,
} from "@xyflow/react";
import { create } from "zustand";

import { saveDraftGraph } from "@/api/workflows";
import type { NodeType, Workflow, WorkflowDebugFrame, WorkflowNode } from "@/types/workflows";
import { layeredLayout } from "./auto-layout";
import { NODE_DEFS } from "./node-registry";
import { EDGE_TYPE, toDraft, toFlow, type WfFlowNode } from "./serialize";
import { wouldCreateCycle } from "./validation";

export type SaveState = "idle" | "saving" | "saved" | "error";

interface EditorState {
  workflow: Workflow | null;
  nodes: WfFlowNode[];
  edges: Edge[];
  selectedNodeId: string | null;
  saveState: SaveState;
  debugOpen: boolean;
  debugRunning: boolean;
  debugFrames: WorkflowDebugFrame[];
  debugByNode: Record<string, WorkflowDebugFrame>;

  init: (workflow: Workflow, graph: { nodes: WorkflowNode[]; edges: never[] } | Parameters<typeof toFlow>[0]) => void;
  reset: () => void;
  setWorkflow: (patch: Partial<Workflow>) => void;

  onNodesChange: (changes: NodeChange[]) => void;
  onEdgesChange: (changes: EdgeChange[]) => void;
  onConnect: (conn: Connection) => void;
  isValidConnection: (conn: Connection | Edge) => boolean;

  addNode: (type: NodeType, position?: { x: number; y: number }) => void;
  removeNode: (id: string) => void;
  updateNodeData: (id: string, patch: Partial<WorkflowNode>) => void;
  setSelected: (id: string | null) => void;
  applyLayout: () => void;

  setDebugOpen: (open: boolean) => void;
  startDebug: () => void;
  endDebug: () => void;
  upsertDebugFrame: (frame: WorkflowDebugFrame) => void;

  scheduleSave: () => void;
  flushSave: () => Promise<boolean>;
}

let saveTimer: ReturnType<typeof setTimeout> | null = null;

function uuid(): string {
  return crypto.randomUUID();
}

/** 在已有标题里取不冲突的自动名：base → base 2 → base 3 … */
function autoTitle(base: string, nodes: WfFlowNode[]): string {
  const used = new Set(nodes.map((n) => n.data.wf.title));
  if (!used.has(base)) return base;
  for (let i = 2; i < 1000; i++) {
    const cand = `${base} ${i}`;
    if (!used.has(cand)) return cand;
  }
  return `${base} ${uuid().slice(0, 4)}`;
}

export const useEditorStore = create<EditorState>((set, get) => ({
  workflow: null,
  nodes: [],
  edges: [],
  selectedNodeId: null,
  saveState: "idle",
  debugOpen: false,
  debugRunning: false,
  debugFrames: [],
  debugByNode: {},

  init: (workflow, graph) => {
    if (saveTimer) {
      clearTimeout(saveTimer);
      saveTimer = null;
    }
    const { nodes, edges } = toFlow(graph as Parameters<typeof toFlow>[0]);
    set({
      workflow,
      nodes,
      edges,
      selectedNodeId: null,
      saveState: "idle",
      debugOpen: false,
      debugRunning: false,
      debugFrames: [],
      debugByNode: {},
    });
  },

  reset: () => {
    if (saveTimer) {
      clearTimeout(saveTimer);
      saveTimer = null;
    }
    set({
      workflow: null,
      nodes: [],
      edges: [],
      selectedNodeId: null,
      saveState: "idle",
      debugOpen: false,
      debugRunning: false,
      debugFrames: [],
      debugByNode: {},
    });
  },

  setWorkflow: (patch) =>
    set((s) => (s.workflow ? { workflow: { ...s.workflow, ...patch } } : {})),

  onNodesChange: (changes) => {
    set((s) => ({ nodes: applyNodeChanges(changes, s.nodes) as WfFlowNode[] }));
    // 只有位置/删除变化才需要落库；选中/尺寸变化忽略。
    if (changes.some((c) => c.type === "position" || c.type === "remove")) get().scheduleSave();
  },

  onEdgesChange: (changes) => {
    set((s) => ({ edges: applyEdgeChanges(changes, s.edges) }));
    if (changes.some((c) => c.type === "remove")) get().scheduleSave();
  },

  onConnect: (conn) => {
    set((s) => ({
      edges: addEdge({ ...conn, id: uuid(), type: EDGE_TYPE }, s.edges),
    }));
    get().scheduleSave();
  },

  isValidConnection: (conn) => {
    const { source, target } = conn;
    if (!source || !target || source === target) return false;
    const { nodes, edges } = get();
    const byId = new Map(nodes.map((n) => [n.id, n.data.wf.node_type]));
    if (byId.get(target) === "start") return false; // start 不能作为目标
    if (byId.get(source) === "end") return false; // end 不能作为来源
    if (edges.some((e) => e.source === source && e.target === target)) return false; // 重复边
    if (wouldCreateCycle(edges, source, target)) return false; // 成环
    return true;
  },

  addNode: (type, position) => {
    const def = NODE_DEFS[type];
    if (!def) return;
    const { nodes } = get();
    if (def.unique && nodes.some((n) => n.data.wf.node_type === type)) return; // start/end 唯一
    const wf: WorkflowNode = {
      id: uuid(),
      node_type: type,
      title: autoTitle(def.label, nodes),
      description: "",
      position: position ?? { x: 120 + nodes.length * 24, y: 120 + nodes.length * 24 },
      ...def.createData(),
    };
    set((s) => ({
      nodes: [
        ...s.nodes,
        { id: wf.id, type, position: wf.position, data: { wf }, deletable: type !== "start" },
      ],
      selectedNodeId: wf.id,
    }));
    get().scheduleSave();
  },

  removeNode: (id) => {
    set((s) => ({
      nodes: s.nodes.filter((n) => n.id !== id),
      edges: s.edges.filter((e) => e.source !== id && e.target !== id),
      selectedNodeId: s.selectedNodeId === id ? null : s.selectedNodeId,
    }));
    get().scheduleSave();
  },

  updateNodeData: (id, patch) => {
    set((s) => ({
      nodes: s.nodes.map((n) =>
        n.id === id ? { ...n, data: { wf: { ...n.data.wf, ...patch } } } : n,
      ),
    }));
    get().scheduleSave();
  },

  setSelected: (id) => set({ selectedNodeId: id }),

  applyLayout: () => {
    const { nodes, edges } = get();
    const pos = layeredLayout(
      nodes.map((n) => n.data.wf),
      edges.map((e) => ({ source: e.source, target: e.target })),
    );
    set((s) => ({
      nodes: s.nodes.map((n) => (pos[n.id] ? { ...n, position: pos[n.id] } : n)),
    }));
    get().scheduleSave();
  },

  setDebugOpen: (open) => set({ debugOpen: open }),
  startDebug: () => set({ debugRunning: true, debugFrames: [], debugByNode: {} }),
  endDebug: () => set({ debugRunning: false }),
  upsertDebugFrame: (frame) =>
    set((s) => {
      const idx = s.debugFrames.findIndex((f) => f.id === frame.id);
      const debugFrames =
        idx === -1
          ? [...s.debugFrames, frame]
          : s.debugFrames.map((f, i) => (i === idx ? frame : f));
      return { debugFrames, debugByNode: { ...s.debugByNode, [frame.node_data.id]: frame } };
    }),

  scheduleSave: () => {
    if (saveTimer) clearTimeout(saveTimer);
    saveTimer = setTimeout(() => {
      void get().flushSave();
    }, 600);
  },

  flushSave: async () => {
    if (saveTimer) {
      clearTimeout(saveTimer);
      saveTimer = null;
    }
    const { workflow, nodes, edges } = get();
    if (!workflow) return false;
    set({ saveState: "saving" });
    try {
      await saveDraftGraph(workflow.id, toDraft(nodes, edges));
      // 存草稿后端会重置调试通过标记，前端同步。
      set((s) => ({
        saveState: "saved",
        workflow: s.workflow ? { ...s.workflow, is_debug_passed: false } : s.workflow,
      }));
      return true;
    } catch {
      set({ saveState: "error" });
      return false;
    }
  },
}));
