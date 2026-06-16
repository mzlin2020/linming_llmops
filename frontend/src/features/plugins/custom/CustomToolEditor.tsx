import { useEffect } from "react";
import { Controller, useFieldArray, useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate, useParams } from "react-router-dom";
import { ArrowLeft, Plus, Trash2 } from "lucide-react";
import { z } from "zod";

import { createApiTool, getApiTool, updateApiTool } from "@/api/plugins";
import { FormError, FormRow } from "@/components/shared/form";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { OpenApiSchemaEditor } from "./OpenApiSchemaEditor";

const schema = z.object({
  name: z.string().min(1, "请输入名称").max(64, "名称最多 64 字"),
  icon: z.string().min(1, "请输入图标 URL").max(512, "URL 过长"),
  openapi_schema: z.string().min(1, "请粘贴 OpenAPI schema"),
  headers: z.array(z.object({ key: z.string(), value: z.string() })),
});
type FormValues = z.infer<typeof schema>;

const EMPTY: FormValues = { name: "", icon: "", openapi_schema: "", headers: [] };

/** 自定义插件 创建/编辑：整页表单（rhf+zod）+ OpenAPI 编辑器。`/plugins/custom/new` 与 `/:id` 共用。 */
export function CustomToolEditor() {
  const { id } = useParams();
  const editing = Boolean(id);
  const providerId = id ? Number(id) : undefined;
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const {
    register,
    handleSubmit,
    control,
    reset,
    formState: { errors },
  } = useForm<FormValues>({ resolver: zodResolver(schema), defaultValues: EMPTY });
  const headers = useFieldArray({ control, name: "headers" });

  const detailQuery = useQuery({
    queryKey: ["api-tool", providerId],
    queryFn: () => getApiTool(providerId!),
    enabled: editing,
  });

  useEffect(() => {
    if (detailQuery.data) {
      reset({
        name: detailQuery.data.name,
        icon: detailQuery.data.icon,
        openapi_schema: detailQuery.data.openapi_schema,
        headers: detailQuery.data.headers ?? [],
      });
    }
  }, [detailQuery.data, reset]);

  const mutation = useMutation({
    mutationFn: (values: FormValues) =>
      editing ? updateApiTool(providerId!, values) : createApiTool(values),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["api-tools"] });
      navigate("/plugins/custom");
    },
  });

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <div className="flex items-center gap-2">
        <Button
          variant="ghost"
          size="icon"
          onClick={() => navigate("/plugins/custom")}
          aria-label="返回"
        >
          <ArrowLeft className="h-4 w-4" />
        </Button>
        <h2 className="text-lg font-semibold">{editing ? "编辑自定义插件" : "新建自定义插件"}</h2>
      </div>

      <form onSubmit={handleSubmit((v) => mutation.mutate(v))} className="space-y-5">
        <FormRow label="名称" htmlFor="name" error={errors.name?.message}>
          <Input id="name" {...register("name")} placeholder="例如 天气查询" />
        </FormRow>
        <FormRow label="图标 URL" htmlFor="icon" error={errors.icon?.message}>
          <Input id="icon" {...register("icon")} placeholder="https://…/icon.png" />
        </FormRow>

        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium">请求头（可选）</span>
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => headers.append({ key: "", value: "" })}
            >
              <Plus className="h-4 w-4" /> 添加
            </Button>
          </div>
          {headers.fields.map((f, i) => (
            <div key={f.id} className="flex items-center gap-2">
              <Input {...register(`headers.${i}.key`)} placeholder="Header" aria-label={`请求头 ${i + 1} 名`} />
              <Input {...register(`headers.${i}.value`)} placeholder="值" aria-label={`请求头 ${i + 1} 值`} />
              <Button
                type="button"
                variant="ghost"
                size="icon"
                onClick={() => headers.remove(i)}
                aria-label="删除请求头"
              >
                <Trash2 className="h-4 w-4" />
              </Button>
            </div>
          ))}
        </div>

        <div className="space-y-1.5">
          <span className="text-sm font-medium">OpenAPI schema</span>
          <Controller
            control={control}
            name="openapi_schema"
            render={({ field }) => (
              <OpenApiSchemaEditor
                value={field.value}
                onChange={field.onChange}
                error={errors.openapi_schema?.message}
              />
            )}
          />
        </div>

        {mutation.isError && <FormError error={mutation.error} />}

        <div className="flex justify-end gap-2">
          <Button type="button" variant="outline" onClick={() => navigate("/plugins/custom")}>
            取消
          </Button>
          <Button type="submit" disabled={mutation.isPending}>
            {editing ? "保存" : "创建"}
          </Button>
        </div>
      </form>
    </div>
  );
}
