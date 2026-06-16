import { useState } from "react";
import { AlertCircle, CheckCircle2, Loader2 } from "lucide-react";

import { validateOpenapiSchema } from "@/api/plugins";
import { Button } from "@/components/ui/button";
import { getErrorMessage } from "@/lib/http/errors";

interface Props {
  value: string;
  onChange: (v: string) => void;
  error?: string;
}

interface ToolPreview {
  name: string;
  description: string;
  method: string;
  path: string;
}

/** 本地解析 schema 出工具预览（仅在服务端校验通过后调用）。 */
function parseToolsPreview(schema: string): ToolPreview[] {
  const parsed = JSON.parse(schema) as {
    paths?: Record<string, Record<string, { operationId?: string; description?: string }>>;
  };
  const out: ToolPreview[] = [];
  for (const [path, methods] of Object.entries(parsed.paths ?? {})) {
    for (const [method, op] of Object.entries(methods)) {
      if (op?.operationId) {
        out.push({
          name: op.operationId,
          description: op.description ?? "",
          method: method.toUpperCase(),
          path,
        });
      }
    }
  }
  return out;
}

/** OpenAPI schema 编辑器：受控等宽 textarea + 服务端校验 + 通过后本地解析工具预览。 */
export function OpenApiSchemaEditor({ value, onChange, error }: Props) {
  const [status, setStatus] = useState<"idle" | "validating" | "ok" | "error">("idle");
  const [message, setMessage] = useState("");
  const [preview, setPreview] = useState<ToolPreview[]>([]);

  const validate = async () => {
    setStatus("validating");
    setMessage("");
    setPreview([]);
    try {
      await validateOpenapiSchema(value);
      setStatus("ok");
      setMessage("校验通过");
      try {
        setPreview(parseToolsPreview(value));
      } catch {
        /* 预览解析失败不影响通过态 */
      }
    } catch (err) {
      setStatus("error");
      setMessage(getErrorMessage(err));
    }
  };

  return (
    <div className="space-y-2">
      <textarea
        value={value}
        onChange={(e) => {
          onChange(e.target.value);
          setStatus("idle");
        }}
        spellCheck={false}
        rows={12}
        aria-label="OpenAPI schema"
        placeholder={'{ "server": "https://api.example.com", "description": "…", "paths": { … } }'}
        className="w-full resize-y rounded-md border border-input bg-transparent p-3 font-mono text-xs leading-relaxed shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
      />

      <div className="flex flex-wrap items-center gap-3">
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={validate}
          disabled={!value.trim() || status === "validating"}
        >
          {status === "validating" && <Loader2 className="h-4 w-4 animate-spin" />}
          校验 schema
        </Button>
        {status === "ok" && (
          <span className="flex items-center gap-1 text-sm text-emerald-600">
            <CheckCircle2 className="h-4 w-4" /> {message}
          </span>
        )}
        {status === "error" && (
          <span role="alert" className="flex items-center gap-1 text-sm text-destructive">
            <AlertCircle className="h-4 w-4" /> {message}
          </span>
        )}
      </div>

      {error && <p className="text-sm text-destructive">{error}</p>}

      {preview.length > 0 && (
        <div className="rounded-md border p-3">
          <p className="mb-2 text-xs font-medium text-muted-foreground">解析出 {preview.length} 个工具</p>
          <ul className="space-y-1">
            {preview.map((t) => (
              <li key={t.name} className="text-sm">
                <span className="font-mono">{t.name}</span>
                <span className="ml-2 text-xs text-muted-foreground">
                  {t.method} {t.path}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
