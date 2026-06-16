import { Button } from "@/components/ui/button";
import { Modal } from "./Modal";

interface Props {
  open: boolean;
  title: string;
  description?: string;
  confirmText?: string;
  cancelText?: string;
  destructive?: boolean;
  loading?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}

/** 极简确认弹窗：基于通用 Modal，补「取消 / 确认」两按钮。用于删除/下架等确认。 */
export function ConfirmDialog({
  open,
  title,
  description,
  confirmText = "确认",
  cancelText = "取消",
  destructive,
  loading,
  onConfirm,
  onCancel,
}: Props) {
  return (
    <Modal
      open={open}
      title={title}
      onClose={onCancel}
      footer={
        <>
          <Button variant="outline" size="sm" onClick={onCancel} disabled={loading}>
            {cancelText}
          </Button>
          <Button
            variant={destructive ? "destructive" : "default"}
            size="sm"
            onClick={onConfirm}
            disabled={loading}
          >
            {confirmText}
          </Button>
        </>
      }
    >
      {description && <p className="text-sm text-muted-foreground">{description}</p>}
    </Modal>
  );
}
