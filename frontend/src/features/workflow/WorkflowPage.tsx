import { Placeholder } from "@/components/shared/Placeholder";

/**
 * 工作流模块 = v1 占位页。后端工作流目前仅 core 库层,无 service/handler/路由;
 * 可视化编辑器(@xyflow/react)随 v1.1 提供。
 */
export function WorkflowPage() {
  return (
    <Placeholder
      title="工作流"
      note="敬请期待 v1.1 — 可视化编排编辑器与后端执行端点"
    />
  );
}
