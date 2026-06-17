import { Plus, Trash2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";
import {
  IDENTIFIER_RE,
  VARIABLE_TYPES,
  declareVar,
  literalVar,
  type VariableEntity,
  type VariableType,
} from "@/types/workflows";
import { SELECT_CLS } from "./controls";
import { ValueEditor } from "./ValueEditor";

interface Props {
  nodeId: string;
  vars: VariableEntity[];
  onChange: (next: VariableEntity[]) => void;
  /** declare：声明变量（名/类型/必填/描述）；value：取值变量（名/类型 + 字面量或引用）。 */
  mode: "declare" | "value";
  showRequired?: boolean;
  showDescription?: boolean;
  /** 只读展示（固定输出）。 */
  fixed?: boolean;
  addLabel?: string;
  emptyText?: string;
}

/** 变量列表编辑器：节点 inputs/outputs 的统一编辑 UI。 */
export function VariableListEditor({
  nodeId,
  vars,
  onChange,
  mode,
  showRequired,
  showDescription,
  fixed,
  addLabel = "添加变量",
  emptyText = "暂无变量",
}: Props) {
  const patch = (i: number, p: Partial<VariableEntity>) =>
    onChange(vars.map((v, idx) => (idx === i ? { ...v, ...p } : v)));
  const remove = (i: number) => onChange(vars.filter((_, idx) => idx !== i));
  const add = () => onChange([...vars, mode === "value" ? literalVar("") : declareVar("")]);

  if (fixed) {
    return (
      <div className="space-y-1">
        {vars.length === 0 ? (
          <p className="text-xs text-muted-foreground">{emptyText}</p>
        ) : (
          vars.map((v) => (
            <div key={v.name} className="flex items-center justify-between rounded-md border bg-muted/30 px-2 py-1 text-xs">
              <span className="font-mono">{v.name}</span>
              <span className="text-muted-foreground">{v.type}</span>
            </div>
          ))
        )}
      </div>
    );
  }

  return (
    <div className="space-y-2">
      {vars.length === 0 && <p className="text-xs text-muted-foreground">{emptyText}</p>}
      {vars.map((v, i) => {
        const nameInvalid = v.name !== "" && !IDENTIFIER_RE.test(v.name);
        return (
          <div key={i} className="space-y-1.5 rounded-md border p-2">
            <div className="flex items-center gap-1.5">
              <Input
                value={v.name}
                placeholder="变量名"
                className={cn("h-8", nameInvalid && "border-destructive")}
                onChange={(e) => patch(i, { name: e.target.value })}
              />
              <select
                className={cn(SELECT_CLS, "h-8")}
                value={v.type}
                onChange={(e) => patch(i, { type: e.target.value as VariableType })}
              >
                {VARIABLE_TYPES.map((t) => (
                  <option key={t} value={t}>
                    {t}
                  </option>
                ))}
              </select>
              {mode === "declare" && showRequired && (
                <label className="inline-flex items-center gap-1 whitespace-nowrap text-xs text-muted-foreground">
                  <input
                    type="checkbox"
                    checked={v.required}
                    onChange={(e) => patch(i, { required: e.target.checked })}
                  />
                  必填
                </label>
              )}
              <Button
                type="button"
                variant="ghost"
                size="icon"
                className="h-8 w-8 shrink-0 text-muted-foreground"
                onClick={() => remove(i)}
                aria-label="删除变量"
              >
                <Trash2 className="h-4 w-4" />
              </Button>
            </div>
            {mode === "value" && (
              <ValueEditor nodeId={nodeId} variable={v} onChange={(value) => patch(i, { value })} />
            )}
            {mode === "declare" && showDescription && (
              <Input
                value={v.description}
                placeholder="描述（可选）"
                className="h-8"
                onChange={(e) => patch(i, { description: e.target.value })}
              />
            )}
          </div>
        );
      })}
      <Button type="button" variant="outline" size="sm" onClick={add}>
        <Plus className="h-4 w-4" /> {addLabel}
      </Button>
    </div>
  );
}
