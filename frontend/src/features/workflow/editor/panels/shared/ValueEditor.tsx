import { Link2, PenLine } from "lucide-react";

import { cn } from "@/lib/utils";
import type { VariableEntity, VariableValue } from "@/types/workflows";
import { TypedValueInput } from "./TypedValueInput";
import { VarRefSelect } from "./VarRefSelect";

interface Props {
  nodeId: string;
  variable: VariableEntity;
  onChange: (value: VariableValue) => void;
}

/** 变量取值编辑：字面量（手填）/ 引用（指向上游输出）二选一。 */
export function ValueEditor({ nodeId, variable, onChange }: Props) {
  const isRef = variable.value.type === "ref";

  return (
    <div className="space-y-1.5">
      <div className="flex gap-1">
        <ModeButton
          active={!isRef}
          onClick={() => onChange({ type: "literal", content: "" })}
          icon={<PenLine className="h-3 w-3" />}
          label="字面量"
        />
        <ModeButton
          active={isRef}
          onClick={() => onChange({ type: "ref", content: { ref_node_id: null, ref_var_name: "" } })}
          icon={<Link2 className="h-3 w-3" />}
          label="引用"
        />
      </div>
      {isRef ? (
        <VarRefSelect
          nodeId={nodeId}
          value={variable.value.type === "ref" ? variable.value.content : null}
          onChange={(ref) => onChange({ type: "ref", content: ref })}
        />
      ) : (
        <TypedValueInput
          type={variable.type}
          value={variable.value.type === "literal" ? variable.value.content : ""}
          onChange={(content) => onChange({ type: "literal", content })}
        />
      )}
    </div>
  );
}

function ModeButton({
  active,
  onClick,
  icon,
  label,
}: {
  active: boolean;
  onClick: () => void;
  icon: React.ReactNode;
  label: string;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "inline-flex items-center gap-1 rounded-md border px-2 py-1 text-xs transition-colors",
        active ? "border-primary bg-primary/5 text-primary" : "text-muted-foreground hover:bg-muted/50",
      )}
    >
      {icon}
      {label}
    </button>
  );
}
