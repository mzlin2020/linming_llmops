/** 工作流端点薄封装。响应经 axios 拦截器解信封后即下列返回值；调试走 SSE（见 use-workflow-debug）。 */
import { get, post } from "@/lib/http/client";
import type { PageQuery, PageResult } from "@/types/api";
import type {
  CreateWorkflowReq,
  DraftGraph,
  UpdateWorkflowReq,
  Workflow,
  WorkflowStatus,
} from "@/types/workflows";

export type WorkflowListQuery = PageQuery & { status?: WorkflowStatus };

// ---------- CRUD ----------

export function listWorkflows(query: WorkflowListQuery): Promise<PageResult<Workflow>> {
  return get<PageResult<Workflow>>("/workflows", { params: query });
}

export function getWorkflow(id: number): Promise<Workflow> {
  return get<Workflow>(`/workflows/${id}`);
}

export function createWorkflow(body: CreateWorkflowReq): Promise<{ id: number }> {
  return post<{ id: number }>("/workflows", body);
}

export function updateWorkflow(id: number, body: UpdateWorkflowReq): Promise<unknown> {
  return post(`/workflows/${id}`, body);
}

export function deleteWorkflow(id: number): Promise<unknown> {
  return post(`/workflows/${id}/delete`);
}

// ---------- 草稿图 ----------

export function getDraftGraph(id: number): Promise<DraftGraph> {
  return get<DraftGraph>(`/workflows/${id}/draft-graph`);
}

/** 保存草稿图（后端宽松校验落库并重置 is_debug_passed）。 */
export function saveDraftGraph(id: number, graph: DraftGraph): Promise<unknown> {
  return post(`/workflows/${id}/draft-graph`, graph);
}

// ---------- 发布 ----------

export function publishWorkflow(id: number): Promise<unknown> {
  return post(`/workflows/${id}/publish`);
}

export function cancelPublishWorkflow(id: number): Promise<unknown> {
  return post(`/workflows/${id}/cancel-publish`);
}

/** 调试端点（SSE，POST）。请求体即工作流入参 {var: value}。 */
export function workflowDebugUrl(id: number): string {
  return `/workflows/${id}/debug`;
}
