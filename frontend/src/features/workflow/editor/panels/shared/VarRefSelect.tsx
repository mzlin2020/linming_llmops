import { useMemo } from "react";

import { cn } from "@/lib/utils";
import type { RefContent } from "@/types/workflows";
import { NODE_DEFS } from "../../node-registry";
import { useEditorStore } from "../../store";
import { getPredecessors, getRefSourceVars } from "../../validation";
import { SELECT_CLS } from "./controls";

interface Props {
  nodeId: string;
  value: RefContent | null;
  onChange: (ref: RefContent) => void;
}

/** 引用选择器：列出当前节点全部前驱节点的可引用输出变量，分组下拉。 */
export function VarRefSelect({ nodeId, value, onChange }: Props) {
  const nodes = useEditorStore((s) => s.nodes);
  const edges = useEditorStore((s) => s.edges);

  const groups = useMemo(() => {
    const wfNodes = nodes.map((n) => n.data.wf);
    const preds = getPredecessors(nodeId, wfNodes, edges);
    return preds
      .map((p) => ({ node: p, vars: getRefSourceVars(p) }))
      .filter((g) => g.vars.length > 0);
  }, [nodes, edges, nodeId]);

  const current = value?.ref_node_id ? `${value.ref_node_id}::${value.ref_var_name}` : "";
  const invalid =
    !!value?.ref_node_id &&
    !groups.some((g) => g.node.id === value.ref_node_id && g.vars.some((v) => v.name === value.ref_var_name));

  return (
    <select
      className={cn(SELECT_CLS, "w-full", invalid && "border-destructive text-destructive")}
      value={invalid ? "" : current}
      onChange={(e) => {
        const [ref_node_id, ref_var_name] = e.target.value.split("::");
        onChange({ ref_node_id: ref_node_id || null, ref_var_name: ref_var_name || "" });
      }}
    >
      <option value="">{invalid ? "引用已失效，请重新选择" : "选择上游变量…"}</option>
      {groups.map((g) => (
        <optgroup key={g.node.id} label={`${g.node.title}（${NODE_DEFS[g.node.node_type]?.label ?? g.node.node_type}）`}>
          {g.vars.map((v) => (
            <option key={`${g.node.id}::${v.name}`} value={`${g.node.id}::${v.name}`}>
              {v.name}
            </option>
          ))}
        </optgroup>
      ))}
    </select>
  );
}
