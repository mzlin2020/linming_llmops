"""大语言模型节点：沙箱渲染 prompt → LanguageModelManager 加载模型 → stream 累积。

max_tokens 钳到 WORKFLOW_LLM_MAX_TOKENS（4GB 主机防长输出拖垮 SSE），
provider/model 缺省回落 DEFAULT_LLM_PROVIDER / DEFAULT_LLM_MODEL（与 chat 链路同源）。
"""
import time
from typing import Optional

from langchain_core.runnables import RunnableConfig

from internal.core.language_model.defaults import resolve_default_provider_model
from internal.core.workflow.entities.node_entity import NodeResult, NodeStatus
from internal.core.workflow.entities.workflow_entity import WorkflowState
from internal.core.workflow.nodes.base_node import BaseNode
from internal.core.workflow.utils.helper import (
    extract_variables_from_state,
    get_config_int,
    render_template_sandboxed,
)

from .llm_entity import LLMNodeData


class LLMNode(BaseNode):
    """大语言模型节点。"""

    node_data: LLMNodeData

    def invoke(self, state: WorkflowState, config: Optional[RunnableConfig] = None) -> WorkflowState:
        start_at = time.perf_counter()
        inputs_dict = extract_variables_from_state(self.node_data.inputs, state)

        # 1.沙箱渲染提示词模板
        prompt_value = render_template_sandboxed(self.node_data.prompt, inputs_dict)

        # 2.解析 provider/model（节点配置优先，缺省与 chat 链路同源回落）
        cfg = self.node_data.language_model_config or {}
        provider, model = resolve_default_provider_model(cfg)

        # 3.参数透传 + max_tokens 钳制
        params = dict(cfg.get("parameters") or {})
        cap = get_config_int("WORKFLOW_LLM_MAX_TOKENS", 1024)
        try:
            requested = int(params.get("max_tokens") or 0)
        except (TypeError, ValueError):
            requested = 0
        params["max_tokens"] = min(requested, cap) if requested > 0 else cap

        # 4.加载模型并流式累积（避免长时间无响应；worker 线程下补 Flask 上下文）
        with self.ensure_app_context():
            from app.http.module import injector
            from internal.core.language_model import LanguageModelManager

            llm = injector.get(LanguageModelManager).instantiate(provider, model, **params)

            content = ""
            for chunk in llm.stream(prompt_value):
                piece = getattr(chunk, "content", "")
                if isinstance(piece, str):
                    content += piece

        # 5.提取并构建输出数据结构
        outputs = {}
        if self.node_data.outputs:
            outputs[self.node_data.outputs[0].name] = content
        else:
            outputs["output"] = content

        return {
            "node_results": [
                NodeResult(
                    node_data=self.node_data,
                    status=NodeStatus.SUCCEEDED,
                    inputs=inputs_dict,
                    outputs=outputs,
                    latency=(time.perf_counter() - start_at),
                )
            ]
        }
