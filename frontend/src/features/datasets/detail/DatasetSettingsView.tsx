import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate, useParams } from "react-router-dom";
import { z } from "zod";

import { deleteDataset, getDataset, updateDataset } from "@/api/datasets";
import { ConfirmDialog } from "@/components/shared/ConfirmDialog";
import { FormError, FormRow } from "@/components/shared/form";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";

const schema = z.object({
  name: z.string().min(1, "请输入名称").max(128, "名称最多 128 字"),
  icon: z.string().max(512, "URL 过长"),
  description: z.string().max(2000, "描述最多 2000 字"),
});
type FormValues = z.infer<typeof schema>;

/** 知识库设置：编辑元信息 + 删除。 */
export function DatasetSettingsView() {
  const { id } = useParams();
  const datasetId = Number(id);
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [confirmDelete, setConfirmDelete] = useState(false);

  const query = useQuery({
    queryKey: ["dataset", datasetId],
    queryFn: () => getDataset(datasetId),
    enabled: Number.isFinite(datasetId),
  });

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { name: "", icon: "", description: "" },
  });

  useEffect(() => {
    if (query.data) {
      reset({
        name: query.data.name,
        icon: query.data.icon,
        description: query.data.description,
      });
    }
  }, [query.data, reset]);

  const updateMutation = useMutation({
    mutationFn: (values: FormValues) => updateDataset(datasetId, values),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["datasets"] });
      queryClient.invalidateQueries({ queryKey: ["dataset", datasetId] });
    },
  });
  const deleteMutation = useMutation({
    mutationFn: () => deleteDataset(datasetId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["datasets"] });
      navigate("/datasets");
    },
  });

  return (
    <div className="max-w-2xl space-y-8">
      <form onSubmit={handleSubmit((v) => updateMutation.mutate(v))} className="space-y-4">
        <FormRow label="名称" htmlFor="name" error={errors.name?.message}>
          <Input id="name" {...register("name")} />
        </FormRow>
        <FormRow label="图标 URL（可选）" htmlFor="icon" error={errors.icon?.message}>
          <Input id="icon" {...register("icon")} placeholder="https://…/icon.png" />
        </FormRow>
        <FormRow label="描述（可选）" htmlFor="description" error={errors.description?.message}>
          <Textarea id="description" rows={3} {...register("description")} />
        </FormRow>
        {updateMutation.isError && <FormError error={updateMutation.error} />}
        <div className="flex items-center gap-3">
          <Button type="submit" disabled={updateMutation.isPending}>
            保存
          </Button>
          {updateMutation.isSuccess && <span className="text-sm text-muted-foreground">已保存</span>}
        </div>
      </form>

      <div className="space-y-2 rounded-lg border border-destructive/30 p-4">
        <h4 className="text-sm font-medium">删除知识库</h4>
        <p className="text-sm text-muted-foreground">删除后文档与片段将一并清除，不可恢复。</p>
        <Button variant="destructive" onClick={() => setConfirmDelete(true)}>
          删除知识库
        </Button>
      </div>

      <ConfirmDialog
        open={confirmDelete}
        title="删除知识库"
        description={`确定删除「${query.data?.name ?? ""}」？此操作不可恢复。`}
        confirmText="删除"
        destructive
        loading={deleteMutation.isPending}
        onConfirm={() => deleteMutation.mutate()}
        onCancel={() => setConfirmDelete(false)}
      />
    </div>
  );
}
