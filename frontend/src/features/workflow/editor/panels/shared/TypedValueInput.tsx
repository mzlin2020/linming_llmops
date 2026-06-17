import { Input } from "@/components/ui/input";
import type { VariableType } from "@/types/workflows";

interface Props {
  type: VariableType;
  value: string | number | boolean;
  onChange: (v: string | number | boolean) => void;
  placeholder?: string;
}

/** 按变量类型渲染输入控件：boolean→勾选框，int/float→数字框，string→文本框。 */
export function TypedValueInput({ type, value, onChange, placeholder }: Props) {
  if (type === "boolean") {
    return (
      <label className="inline-flex h-9 items-center gap-2 text-sm">
        <input
          type="checkbox"
          checked={Boolean(value)}
          onChange={(e) => onChange(e.target.checked)}
        />
        {String(Boolean(value))}
      </label>
    );
  }
  if (type === "int" || type === "float") {
    return (
      <Input
        type="number"
        step={type === "int" ? 1 : "any"}
        value={value === "" ? "" : Number(value)}
        placeholder={placeholder}
        onChange={(e) => onChange(e.target.value === "" ? "" : Number(e.target.value))}
      />
    );
  }
  return (
    <Input
      value={String(value ?? "")}
      placeholder={placeholder}
      onChange={(e) => onChange(e.target.value)}
    />
  );
}
