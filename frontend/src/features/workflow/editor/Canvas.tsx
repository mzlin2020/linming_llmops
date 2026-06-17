import { useMemo } from "react";
import {
  Background,
  Controls,
  ReactFlow,
  type EdgeTypes,
  type NodeTypes,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";

import { DeletableEdge } from "./edges/DeletableEdge";
import { BaseNode } from "./nodes/BaseNode";
import { EDGE_TYPE } from "./serialize";
import { useEditorStore } from "./store";

const NODE_TYPES: NodeTypes = {
  start: BaseNode,
  end: BaseNode,
  llm: BaseNode,
  template_transform: BaseNode,
  tool: BaseNode,
  dataset_retrieval: BaseNode,
  http_request: BaseNode,
  code: BaseNode,
};

const EDGE_TYPES: EdgeTypes = { [EDGE_TYPE]: DeletableEdge };

const DEFAULT_EDGE_OPTIONS = { type: EDGE_TYPE };

/** ReactFlow 画布：节点/边受控于 zustand store，单击选中节点驱动右侧属性面板。 */
export function Canvas() {
  const nodes = useEditorStore((s) => s.nodes);
  const edges = useEditorStore((s) => s.edges);
  const onNodesChange = useEditorStore((s) => s.onNodesChange);
  const onEdgesChange = useEditorStore((s) => s.onEdgesChange);
  const onConnect = useEditorStore((s) => s.onConnect);
  const isValidConnection = useEditorStore((s) => s.isValidConnection);
  const setSelected = useEditorStore((s) => s.setSelected);

  // ReactFlow 要求 nodeTypes/edgeTypes 引用稳定，模块级常量即可。
  const nodeTypes = useMemo(() => NODE_TYPES, []);
  const edgeTypes = useMemo(() => EDGE_TYPES, []);

  return (
    <ReactFlow
      nodes={nodes}
      edges={edges}
      onNodesChange={onNodesChange}
      onEdgesChange={onEdgesChange}
      onConnect={onConnect}
      isValidConnection={isValidConnection}
      nodeTypes={nodeTypes}
      edgeTypes={edgeTypes}
      defaultEdgeOptions={DEFAULT_EDGE_OPTIONS}
      onNodeClick={(_, node) => setSelected(node.id)}
      onPaneClick={() => setSelected(null)}
      fitView
      proOptions={{ hideAttribution: false }}
    >
      <Background />
      <Controls />
    </ReactFlow>
  );
}
