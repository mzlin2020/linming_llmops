import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { FileText, Loader2, X } from "lucide-react";

import { createDocuments, uploadFile } from "@/api/datasets";
import { FileDropzone } from "@/components/shared/FileDropzone";
import { FormError } from "@/components/shared/form";
import { Modal } from "@/components/shared/Modal";
import { Button } from "@/components/ui/button";
import { getErrorMessage } from "@/lib/http/errors";
import {
  DEFAULT_PROCESS_RULE,
  UPLOAD_ACCEPT_EXTENSIONS,
  validateProcessRule,
  type ProcessRule,
  type ProcessType,
} from "@/types/datasets";
import { ProcessRuleForm } from "./ProcessRuleForm";

interface Props {
  open: boolean;
  datasetId: number;
  onClose: () => void;
  onUploaded: () => void;
}

interface Pending {
  file: File;
  status: "uploading" | "done" | "error";
  uploadFileId?: number;
  error?: string;
}

/** 上传文档：选文件→逐个上传登记→选切分规则→批量建文档。 */
export function DocumentUploadModal({ open, datasetId, onClose, onUploaded }: Props) {
  const [items, setItems] = useState<Pending[]>([]);
  const [processType, setProcessType] = useState<ProcessType>("automatic");
  const [rule, setRule] = useState<ProcessRule>(DEFAULT_PROCESS_RULE);

  const close = () => {
    setItems([]);
    setProcessType("automatic");
    setRule(DEFAULT_PROCESS_RULE);
    onClose();
  };

  const patch = (file: File, next: Partial<Pending>) =>
    setItems((prev) => prev.map((it) => (it.file === file ? { ...it, ...next } : it)));

  const addFiles = (files: File[]) => {
    files.forEach((file) => {
      setItems((prev) => [...prev, { file, status: "uploading" }]);
      uploadFile(file)
        .then((rec) => patch(file, { status: "done", uploadFileId: rec.id }))
        .catch((err) => patch(file, { status: "error", error: getErrorMessage(err) }));
    });
  };

  const removeItem = (file: File) => setItems((prev) => prev.filter((it) => it.file !== file));

  const readyIds = items
    .filter((it) => it.status === "done" && it.uploadFileId)
    .map((it) => it.uploadFileId!);
  const uploading = items.some((it) => it.status === "uploading");
  // 自定义切分规则的前端校验（automatic 用后端默认，免校验）。
  const ruleError = processType === "custom" ? validateProcessRule(rule) : null;

  const createMutation = useMutation({
    mutationFn: () =>
      createDocuments(datasetId, {
        upload_file_ids: readyIds,
        process_type: processType,
        rule: processType === "custom" ? rule : undefined,
      }),
    onSuccess: () => {
      onUploaded();
      close();
    },
  });

  return (
    <Modal open={open} title="上传文档" onClose={close} className="max-w-xl">
      <div className="space-y-4">
        <FileDropzone
          accept={UPLOAD_ACCEPT_EXTENSIONS}
          onFiles={addFiles}
          disabled={createMutation.isPending}
        />

        {items.length > 0 && (
          <ul className="space-y-1">
            {items.map((it) => (
              <li
                key={`${it.file.name}-${it.file.size}`}
                className="flex items-center gap-2 rounded-md border p-2 text-sm"
              >
                <FileText className="h-4 w-4 shrink-0 text-muted-foreground" />
                <span className="min-w-0 flex-1 truncate">{it.file.name}</span>
                {it.status === "uploading" && (
                  <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
                )}
                {it.status === "done" && <span className="text-xs text-green-600">已上传</span>}
                {it.status === "error" && (
                  <span className="truncate text-xs text-destructive" title={it.error}>
                    {it.error || "上传失败"}
                  </span>
                )}
                <button
                  type="button"
                  onClick={() => removeItem(it.file)}
                  aria-label={`移除 ${it.file.name}`}
                  className="text-muted-foreground hover:text-foreground"
                >
                  <X className="h-4 w-4" />
                </button>
              </li>
            ))}
          </ul>
        )}

        <ProcessRuleForm
          processType={processType}
          rule={rule}
          onProcessTypeChange={setProcessType}
          onRuleChange={setRule}
        />

        {ruleError && <p className="text-sm text-destructive">{ruleError}</p>}
        {createMutation.isError && <FormError error={createMutation.error} />}

        <div className="flex justify-end gap-2 pt-1">
          <Button variant="outline" onClick={close} disabled={createMutation.isPending}>
            取消
          </Button>
          <Button
            onClick={() => createMutation.mutate()}
            disabled={
              readyIds.length === 0 || uploading || createMutation.isPending || !!ruleError
            }
          >
            {createMutation.isPending && <Loader2 className="h-4 w-4 animate-spin" />}
            创建{readyIds.length > 0 ? ` (${readyIds.length})` : ""}
          </Button>
        </div>
      </div>
    </Modal>
  );
}
