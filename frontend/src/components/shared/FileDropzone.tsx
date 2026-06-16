import { useRef, useState, type DragEvent } from "react";
import { UploadCloud } from "lucide-react";

import { cn } from "@/lib/utils";

interface Props {
  /** 允许的扩展名（小写、无点）；空数组表示不限。仅客户端提示，后端为准。 */
  accept?: string[];
  onFiles: (files: File[]) => void;
  disabled?: boolean;
}

/** 拖拽 / 点击多选文件，发出 File[]。 */
export function FileDropzone({ accept = [], onFiles, disabled }: Props) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);

  const acceptAttr = accept.map((e) => `.${e}`).join(",");

  const emit = (fileList: FileList | null) => {
    if (fileList && fileList.length) onFiles(Array.from(fileList));
  };

  const onDrop = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setDragging(false);
    if (!disabled) emit(e.dataTransfer.files);
  };

  return (
    <div
      role="button"
      tabIndex={0}
      aria-label="选择或拖拽文件上传"
      onClick={() => !disabled && inputRef.current?.click()}
      onKeyDown={(e) => {
        if ((e.key === "Enter" || e.key === " ") && !disabled) inputRef.current?.click();
      }}
      onDragOver={(e) => {
        e.preventDefault();
        if (!disabled) setDragging(true);
      }}
      onDragLeave={() => setDragging(false)}
      onDrop={onDrop}
      className={cn(
        "flex cursor-pointer flex-col items-center justify-center gap-2 rounded-lg border border-dashed p-8 text-center text-sm transition-colors",
        dragging ? "border-primary bg-primary/5" : "hover:bg-muted/50",
        disabled && "cursor-not-allowed opacity-50 hover:bg-transparent",
      )}
    >
      <UploadCloud className="size-6 text-muted-foreground" />
      <p className="font-medium">点击或拖拽文件到此处上传</p>
      {accept.length > 0 && (
        <p className="text-xs text-muted-foreground">支持 {accept.join(" / ")}</p>
      )}
      <input
        ref={inputRef}
        type="file"
        multiple
        accept={acceptAttr || undefined}
        className="hidden"
        disabled={disabled}
        onChange={(e) => {
          emit(e.target.files);
          e.target.value = ""; // 允许重复选择同一文件
        }}
      />
    </div>
  );
}
