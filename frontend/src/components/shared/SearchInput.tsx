import { useEffect, useRef, useState } from "react";
import { Search } from "lucide-react";

import { Input } from "@/components/ui/input";

interface Props {
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  delay?: number;
}

/** 防抖搜索框：本地即时回显，防抖后回调上层（驱动 search_word + 重置分页）。 */
export function SearchInput({ value, onChange, placeholder = "搜索…", delay = 300 }: Props) {
  const [local, setLocal] = useState(value);
  const onChangeRef = useRef(onChange);
  onChangeRef.current = onChange;

  // 外部 value 变化（如清空）时同步本地。
  useEffect(() => {
    setLocal(value);
  }, [value]);

  // 本地输入与外部值不一致时，防抖回调；一致则不触发（含挂载首帧）。
  useEffect(() => {
    if (local === value) return;
    const t = setTimeout(() => onChangeRef.current(local), delay);
    return () => clearTimeout(t);
  }, [local, value, delay]);

  return (
    <div className="relative w-full max-w-xs">
      <Search className="pointer-events-none absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
      <Input
        value={local}
        onChange={(e) => setLocal(e.target.value)}
        placeholder={placeholder}
        aria-label="搜索"
        className="pl-8"
      />
    </div>
  );
}
