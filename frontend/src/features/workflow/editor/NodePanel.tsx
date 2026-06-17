import type { ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import { Trash2 } from "lucide-react";

import { listApiTools, listBuiltinTools } from "@/api/plugins";
import { listLanguageModels } from "@/api/apps";
import { DatasetSelector } from "@/components/shared/DatasetSelector";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/utils";
import { pickLabel } from "@/types/apps";
import {
  HTTP_METHODS,
  RETRIEVAL_STRATEGIES,
  literalVar,
  type HttpInputLocation,
  type HttpMethod,
  type NodeModelConfig,
  type RetrievalStrategy,
  type VariableEntity,
  type VariableType,
  type WorkflowNode,
} from "@/types/workflows";
import { NODE_DEFS } from "./node-registry";
import { useEditorStore } from "./store";
import { SELECT_CLS } from "./panels/shared/controls";
import { ValueEditor } from "./panels/shared/ValueEditor";
import { VariableListEditor } from "./panels/shared/VariableListEditor";

interface BodyProps {
  node: WorkflowNode;
  onPatch: (patch: Partial<WorkflowNode>) => void;
}

/** 右侧属性面板：通用头（标题/描述/删除）+ 按节点类型分发的配置体。 */
export function NodePanel({ nodeId }: { nodeId: string }) {
  const node = useEditorStore((s) => s.nodes.find((n) => n.id === nodeId)?.data.wf);
  const updateNodeData = useEditorStore((s) => s.updateNodeData);
  const removeNode = useEditorStore((s) => s.removeNode);
  if (!node) return null;

  const onPatch = (patch: Partial<WorkflowNode>) => updateNodeData(node.id, patch);
  const def = NODE_DEFS[node.node_type];

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-start justify-between gap-2 border-b px-4 py-3">
        <div className="min-w-0">
          <p className="text-xs text-muted-foreground">{def?.label ?? node.node_type}</p>
          <Input
            value={node.title}
            onChange={(e) => onPatch({ title: e.target.value })}
            className="mt-1 h-8 font-medium"
          />
        </div>
        {node.node_type !== "start" && (
          <Button
            variant="ghost"
            size="icon"
            className="shrink-0 text-muted-foreground"
            onClick={() => removeNode(node.id)}
            aria-label="删除节点"
          >
            <Trash2 className="h-4 w-4" />
          </Button>
        )}
      </div>

      <div className="flex-1 space-y-4 overflow-auto px-4 py-3">
        <Field label="描述（可选）">
          <Input value={node.description} onChange={(e) => onPatch({ description: e.target.value })} />
        </Field>
        <Body node={node} onPatch={onPatch} />
      </div>
    </div>
  );
}

function Body({ node, onPatch }: BodyProps) {
  switch (node.node_type) {
    case "start":
      return <StartBody node={node} onPatch={onPatch} />;
    case "end":
      return <EndBody node={node} onPatch={onPatch} />;
    case "llm":
      return <LlmBody node={node} onPatch={onPatch} />;
    case "template_transform":
      return <TemplateBody node={node} onPatch={onPatch} />;
    case "tool":
      return <ToolBody node={node} onPatch={onPatch} />;
    case "dataset_retrieval":
      return <DatasetBody node={node} onPatch={onPatch} />;
    case "http_request":
      return <HttpBody node={node} onPatch={onPatch} />;
    case "code":
      return <CodeBody node={node} onPatch={onPatch} />;
    default:
      return null;
  }
}

// ---------------- 各节点体 ----------------

function StartBody({ node, onPatch }: BodyProps) {
  return (
    <Field label="工作流入参" hint="作为工作流被调用时的输入参数">
      <VariableListEditor
        nodeId={node.id}
        vars={node.inputs ?? []}
        onChange={(inputs) => onPatch({ inputs })}
        mode="declare"
        showRequired
        showDescription
        addLabel="添加入参"
        emptyText="暂无入参"
      />
    </Field>
  );
}

function EndBody({ node, onPatch }: BodyProps) {
  return (
    <Field label="工作流输出" hint="引用上游节点的输出作为最终结果">
      <VariableListEditor
        nodeId={node.id}
        vars={node.outputs ?? []}
        onChange={(outputs) => onPatch({ outputs })}
        mode="value"
        addLabel="添加输出"
        emptyText="暂无输出"
      />
    </Field>
  );
}

function LlmBody({ node, onPatch }: BodyProps) {
  const cfg = node.model_config ?? { provider: "", model: "", parameters: {} };
  return (
    <>
      <Field label="模型">
        <ModelSelect value={cfg} onChange={(model_config) => onPatch({ model_config })} />
      </Field>
      <Field label="提示词" hint="Jinja2 模板，用 {{ 变量名 }} 引用下方输入">
        <Textarea
          rows={6}
          value={node.prompt ?? ""}
          onChange={(e) => onPatch({ prompt: e.target.value })}
          placeholder="你是助手，请回答：{{ query }}"
        />
      </Field>
      <Field label="输入变量">
        <VariableListEditor
          nodeId={node.id}
          vars={node.inputs ?? []}
          onChange={(inputs) => onPatch({ inputs })}
          mode="value"
        />
      </Field>
      <Field label="输出（固定）">
        <VariableListEditor nodeId={node.id} vars={node.outputs ?? []} onChange={() => {}} mode="value" fixed />
      </Field>
    </>
  );
}

function TemplateBody({ node, onPatch }: BodyProps) {
  return (
    <>
      <Field label="模板" hint="Jinja2 模板，用 {{ 变量名 }} 引用下方输入">
        <Textarea
          rows={5}
          value={node.template ?? ""}
          onChange={(e) => onPatch({ template: e.target.value })}
          placeholder="你好，{{ name }}"
        />
      </Field>
      <Field label="输入变量">
        <VariableListEditor
          nodeId={node.id}
          vars={node.inputs ?? []}
          onChange={(inputs) => onPatch({ inputs })}
          mode="value"
        />
      </Field>
      <Field label="输出（固定）">
        <VariableListEditor nodeId={node.id} vars={node.outputs ?? []} onChange={() => {}} mode="value" fixed />
      </Field>
    </>
  );
}

function ToolBody({ node, onPatch }: BodyProps) {
  return (
    <>
      <Field label="选择工具">
        <ToolPicker node={node} onPatch={onPatch} />
      </Field>
      <Field label="输入变量">
        <VariableListEditor
          nodeId={node.id}
          vars={node.inputs ?? []}
          onChange={(inputs) => onPatch({ inputs })}
          mode="value"
        />
      </Field>
      <Field label="输出（固定）">
        <VariableListEditor nodeId={node.id} vars={node.outputs ?? []} onChange={() => {}} mode="value" fixed />
      </Field>
    </>
  );
}

function DatasetBody({ node, onPatch }: BodyProps) {
  const rc = node.retrieval_config ?? { retrieval_strategy: "semantic", k: 4, score: 0 };
  const query = node.inputs?.[0];
  return (
    <>
      <Field label="知识库" hint="最多 5 个，仅本人已建的库">
        <DatasetSelector value={node.dataset_ids ?? []} onChange={(ids) => onPatch({ dataset_ids: ids })} />
      </Field>
      <Field label="检索配置">
        <div className="space-y-2">
          <select
            className={cn(SELECT_CLS, "w-full")}
            value={rc.retrieval_strategy}
            onChange={(e) => onPatch({ retrieval_config: { ...rc, retrieval_strategy: e.target.value as RetrievalStrategy } })}
          >
            {RETRIEVAL_STRATEGIES.map((s) => (
              <option key={s} value={s}>
                {s === "semantic" ? "语义检索" : s === "full_text" ? "全文检索" : "混合检索"}
              </option>
            ))}
          </select>
          <div className="flex gap-2">
            <label className="flex-1 text-xs text-muted-foreground">
              k（召回数）
              <Input
                type="number"
                min={1}
                max={10}
                value={rc.k}
                onChange={(e) => onPatch({ retrieval_config: { ...rc, k: Number(e.target.value) } })}
              />
            </label>
            <label className="flex-1 text-xs text-muted-foreground">
              score（阈值）
              <Input
                type="number"
                step="0.01"
                min={0}
                max={0.99}
                value={rc.score}
                onChange={(e) => onPatch({ retrieval_config: { ...rc, score: Number(e.target.value) } })}
              />
            </label>
          </div>
        </div>
      </Field>
      <Field label="查询输入（query）" hint="检索用的查询文本，通常引用开始节点的入参">
        {query && (
          <ValueEditor
            nodeId={node.id}
            variable={query}
            onChange={(value) => onPatch({ inputs: [{ ...query, name: "query", value }] })}
          />
        )}
      </Field>
      <Field label="输出（固定）">
        <VariableListEditor nodeId={node.id} vars={node.outputs ?? []} onChange={() => {}} mode="value" fixed />
      </Field>
    </>
  );
}

const HTTP_LOCS: { key: HttpInputLocation; label: string }[] = [
  { key: "params", label: "Query 参数" },
  { key: "headers", label: "请求头" },
  { key: "body", label: "请求体" },
];

function HttpBody({ node, onPatch }: BodyProps) {
  const inputs = node.inputs ?? [];
  const locOf = (v: VariableEntity): HttpInputLocation =>
    (v.meta?.type as HttpInputLocation) ?? "params";
  const setLoc = (loc: HttpInputLocation, next: VariableEntity[]) => {
    const tagged = next.map((v) => ({ ...v, meta: { ...v.meta, type: loc } }));
    const others = inputs.filter((v) => locOf(v) !== loc);
    onPatch({ inputs: [...others, ...tagged] });
  };
  return (
    <>
      <Field label="请求">
        <div className="flex gap-2">
          <select
            className={cn(SELECT_CLS, "shrink-0 uppercase")}
            value={node.method ?? "get"}
            onChange={(e) => onPatch({ method: e.target.value as HttpMethod })}
          >
            {HTTP_METHODS.map((m) => (
              <option key={m} value={m}>
                {m.toUpperCase()}
              </option>
            ))}
          </select>
          <Input
            value={node.url ?? ""}
            placeholder="https://api.example.com/..."
            onChange={(e) => onPatch({ url: e.target.value })}
          />
        </div>
      </Field>
      {HTTP_LOCS.map(({ key, label }) => (
        <Field key={key} label={label}>
          <VariableListEditor
            nodeId={node.id}
            vars={inputs.filter((v) => locOf(v) === key)}
            onChange={(next) => setLoc(key, next)}
            mode="value"
            addLabel="添加字段"
            emptyText="无"
          />
        </Field>
      ))}
      <Field label="输出（固定）">
        <VariableListEditor nodeId={node.id} vars={node.outputs ?? []} onChange={() => {}} mode="value" fixed />
      </Field>
    </>
  );
}

function CodeBody({ node, onPatch }: BodyProps) {
  return (
    <>
      <Field label="Python 代码" hint="实现 main(params)，返回 dict；在三层沙箱中执行">
        <Textarea
          rows={10}
          value={node.code ?? ""}
          onChange={(e) => onPatch({ code: e.target.value })}
          className="font-mono text-xs"
          spellCheck={false}
        />
      </Field>
      <Field label="输入变量">
        <VariableListEditor
          nodeId={node.id}
          vars={node.inputs ?? []}
          onChange={(inputs) => onPatch({ inputs })}
          mode="value"
        />
      </Field>
      <Field label="输出变量">
        <VariableListEditor
          nodeId={node.id}
          vars={node.outputs ?? []}
          onChange={(outputs) => onPatch({ outputs })}
          mode="declare"
          addLabel="添加输出"
          emptyText="暂无输出"
        />
      </Field>
    </>
  );
}

// ---------------- 子组件 ----------------

function ModelSelect({
  value,
  onChange,
}: {
  value: NodeModelConfig;
  onChange: (v: NodeModelConfig) => void;
}) {
  const { data: providers = [] } = useQuery({ queryKey: ["language-models"], queryFn: listLanguageModels });
  const provider = providers.find((p) => p.name === value.provider);
  return (
    <div className="flex gap-2">
      <select
        className={cn(SELECT_CLS, "flex-1")}
        value={value.provider}
        onChange={(e) => onChange({ ...value, provider: e.target.value, model: "" })}
      >
        <option value="">选择供应商</option>
        {providers.map((p) => (
          <option key={p.name} value={p.name}>
            {pickLabel(p.label, p.name)}
          </option>
        ))}
      </select>
      <select
        className={cn(SELECT_CLS, "flex-1")}
        value={value.model}
        disabled={!provider}
        onChange={(e) => onChange({ ...value, model: e.target.value })}
      >
        <option value="">选择模型</option>
        {provider?.models.map((m) => (
          <option key={m.model_name} value={m.model_name}>
            {pickLabel(m.label, m.model_name)}
          </option>
        ))}
      </select>
    </div>
  );
}

function toVarType(t: string): VariableType {
  const s = (t || "").toLowerCase();
  if (s.includes("int")) return "int";
  if (s.includes("float") || s.includes("number") || s.includes("double")) return "float";
  if (s.includes("bool")) return "boolean";
  return "string";
}

function ToolPicker({ node, onPatch }: BodyProps) {
  const { data: builtins = [] } = useQuery({ queryKey: ["builtin-tools"], queryFn: listBuiltinTools });
  const { data: apiPage } = useQuery({
    queryKey: ["api-tools", "selector"],
    queryFn: () => listApiTools({ current_page: 1, page_size: 50 }),
  });

  const selectInputs = (schema: { name: string; type: string }[]) =>
    schema.map((ti) => literalVar(ti.name, toVarType(ti.type)));

  const isSel = (kind: string, pid: string, tid: string) =>
    node.type === kind && node.provider_id === pid && node.tool_id === tid;

  return (
    <div className="space-y-3">
      <ToolGroup title="内置工具">
        {builtins.flatMap((p) =>
          p.tools.map((t) => (
            <ToolRow
              key={`b:${p.name}:${t.name}`}
              label={t.label || t.name}
              sub={`${p.label || p.name} · ${t.description}`}
              selected={isSel("builtin_tool", p.name, t.name)}
              disabled={p.admin_only}
              onClick={() =>
                onPatch({
                  type: "builtin_tool",
                  provider_id: p.name,
                  tool_id: t.name,
                  params: {},
                  inputs: selectInputs(t.inputs),
                })
              }
            />
          )),
        )}
      </ToolGroup>
      <ToolGroup title="自定义 API 工具">
        {(apiPage?.list ?? []).flatMap((p) =>
          p.tools.map((t) => (
            <ToolRow
              key={`a:${p.id}:${t.name}`}
              label={t.name}
              sub={`${p.name} · ${t.description}`}
              selected={isSel("api_tool", String(p.id), t.name)}
              onClick={() =>
                onPatch({
                  type: "api_tool",
                  provider_id: String(p.id),
                  tool_id: t.name,
                  params: {},
                  inputs: selectInputs(t.inputs),
                })
              }
            />
          )),
        )}
      </ToolGroup>
    </div>
  );
}

function ToolGroup({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div>
      <h4 className="mb-1 text-xs font-medium text-muted-foreground">{title}</h4>
      <div className="space-y-1">{children}</div>
    </div>
  );
}

function ToolRow({
  label,
  sub,
  selected,
  disabled,
  onClick,
}: {
  label: string;
  sub: string;
  selected: boolean;
  disabled?: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      disabled={disabled}
      onClick={onClick}
      className={cn(
        "block w-full rounded-md border p-2 text-left text-sm transition-colors hover:bg-muted/50",
        selected && "border-primary bg-primary/5",
        disabled && "cursor-not-allowed opacity-50 hover:bg-transparent",
      )}
    >
      <span className="block font-medium">{label}</span>
      <span className="block truncate text-xs text-muted-foreground">{sub}</span>
    </button>
  );
}

function Field({ label, hint, children }: { label: string; hint?: string; children: ReactNode }) {
  return (
    <div className="space-y-1.5">
      <div className="text-xs font-medium">{label}</div>
      {hint && <p className="text-xs text-muted-foreground">{hint}</p>}
      {children}
    </div>
  );
}
