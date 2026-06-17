import { useEffect } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { z } from "zod";

import { createWorkflow, updateWorkflow } from "@/api/workflows";
import { FormError, FormRow } from "@/components/shared/form";
import { Modal } from "@/components/shared/Modal";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { IDENTIFIER_RE, type Workflow } from "@/types/workflows";

const schema = z.object({
  name: z.string().min(1, "请输入名称").max(64, "名称最多 64 字"),
  tool_call_name: z
    .string()
    .min(1, "请输入工具调用名")
    .max(64, "最多 64 字")
    .regex(IDENTIFIER_RE, "只能含字母/数字/下划线，且不能以数字开头"),
  icon: z.string().max(512).optional(),
  description: z.string().min(1, "请输入描述（供 AI 判断何时调用）").max(1024, "描述最多 1024 字"),
});
type FormValues = z.infer<typeof schema>;

interface Props {
  open: boolean;
  onClose: () => void;
  /** 传入则为编辑模式；不传为新建（创建成功后进入编辑器）。 */
  workflow?: Workflow | null;
}

/** 工作流元信息表单：新建 / 编辑名称、工具调用名、图标、描述。 */
export function WorkflowFormDialog({ open, onClose, workflow }: Props) {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const editing = !!workflow;

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<FormValues>({ resolver: zodResolver(schema) });

  useEffect(() => {
    if (!open) return;
    reset(
      workflow
        ? {
            name: workflow.name,
            tool_call_name: workflow.tool_call_name,
            icon: workflow.icon,
            description: workflow.description,
          }
        : { name: "", tool_call_name: "", icon: "", description: "" },
    );
  }, [open, workflow, reset]);

  const mutation = useMutation({
    mutationFn: (values: FormValues) =>
      editing ? updateWorkflow(workflow!.id, values) : createWorkflow(values as Required<FormValues>),
    onSuccess: (res) => {
      queryClient.invalidateQueries({ queryKey: ["workflows"] });
      if (editing) {
        queryClient.invalidateQueries({ queryKey: ["workflow", workflow!.id] });
        onClose();
      } else {
        onClose();
        navigate(`/workflow/${(res as { id: number }).id}`);
      }
    },
  });

  return (
    <Modal open={open} title={editing ? "编辑工作流" : "新建工作流"} onClose={onClose} className="max-w-lg">
      <form onSubmit={handleSubmit((v) => mutation.mutate(v))} className="space-y-4">
        <FormRow label="名称" htmlFor="wf-name" error={errors.name?.message}>
          <Input id="wf-name" {...register("name")} placeholder="例如 天气查询流程" />
        </FormRow>
        <FormRow label="工具调用名" htmlFor="wf-tcn" error={errors.tool_call_name?.message}>
          <Input id="wf-tcn" {...register("tool_call_name")} placeholder="weather_lookup（暴露给 LLM 的标识符）" />
        </FormRow>
        <FormRow label="图标（可选，emoji 或 URL）" htmlFor="wf-icon" error={errors.icon?.message}>
          <Input id="wf-icon" {...register("icon")} placeholder="🔧" />
        </FormRow>
        <FormRow label="描述" htmlFor="wf-desc" error={errors.description?.message}>
          <Textarea
            id="wf-desc"
            rows={3}
            {...register("description")}
            placeholder="这个工作流做什么——AI 会据此判断何时调用它"
          />
        </FormRow>

        {mutation.isError && <FormError error={mutation.error} />}

        <div className="flex justify-end gap-2 pt-1">
          <Button type="button" variant="outline" onClick={onClose} disabled={mutation.isPending}>
            取消
          </Button>
          <Button type="submit" disabled={mutation.isPending}>
            {editing ? "保存" : "创建"}
          </Button>
        </div>
      </form>
    </Modal>
  );
}
