"""HTTP 请求节点。

安全/健壮性设计：
- 复用自定义 API 工具的 safe_request（SSRF 守卫 + 逐跳重定向校验 + 默认超时），
  不再裸调 requests.{method}；
- 流式读响应体并按 WORKFLOW_HTTP_MAX_RESPONSE_BYTES 截断，防大响应撑爆内存。
"""
import time
from typing import Optional

from langchain_core.runnables import RunnableConfig

from internal.core.tools.api_tools.providers._safe_http import UnsafeRequestError, safe_request
from internal.core.workflow.entities.node_entity import NodeResult, NodeStatus
from internal.core.workflow.entities.workflow_entity import WorkflowState
from internal.core.workflow.nodes.base_node import BaseNode
from internal.core.workflow.utils.helper import extract_variables_from_state, get_config_int
from internal.exception import FailException

from .http_request_entity import HttpRequestInputType, HttpRequestMethod, HttpRequestNodeData


class HttpRequestNode(BaseNode):
    """HTTP 请求节点。"""

    node_data: HttpRequestNodeData

    def invoke(self, state: WorkflowState, config: Optional[RunnableConfig] = None) -> WorkflowState:
        start_at = time.perf_counter()
        _inputs_dict = extract_variables_from_state(self.node_data.inputs, state)

        if self.node_data.url is None:
            raise FailException(message="HTTP请求节点未配置URL")

        # 1.按 meta.type 把输入归类到 params/headers/body
        inputs_dict = {
            HttpRequestInputType.PARAMS: {},
            HttpRequestInputType.HEADERS: {},
            HttpRequestInputType.BODY: {},
        }
        for input in self.node_data.inputs:
            inputs_dict[input.meta.get("type")][input.name] = _inputs_dict.get(input.name)

        # 2.统一经 safe_request 发请求（SSRF 守卫 + 超时 + 手动逐跳重定向）
        max_bytes = get_config_int("WORKFLOW_HTTP_MAX_RESPONSE_BYTES", 1048576)
        kwargs = dict(
            headers={k: str(v) for k, v in inputs_dict[HttpRequestInputType.HEADERS].items()},
            params=inputs_dict[HttpRequestInputType.PARAMS],
            timeout=get_config_int("WORKFLOW_HTTP_TIMEOUT", 10),
            stream=True,
        )
        if self.node_data.method != HttpRequestMethod.GET:
            kwargs["data"] = inputs_dict[HttpRequestInputType.BODY]

        try:
            response = safe_request(self.node_data.method.value, str(self.node_data.url), **kwargs)
        except UnsafeRequestError as e:
            raise FailException(message=f"HTTP请求目标不安全：{e}")
        except Exception as e:
            raise FailException(message=f"HTTP请求失败：{type(e).__name__}: {str(e)[:200]}")

        # 3.流式读响应体并截断（bytearray 追加，避免 bytes += 的二次方拷贝）
        try:
            buf = bytearray()
            truncated = False
            for chunk in response.iter_content(chunk_size=8192):
                buf.extend(chunk)
                if len(buf) >= max_bytes:
                    del buf[max_bytes:]
                    truncated = True
                    break
            status_code = response.status_code
        finally:
            response.close()

        text = bytes(buf).decode(response.encoding or "utf-8", errors="replace")
        if truncated:
            text += "\n...[响应体超过大小上限，已截断]"

        outputs = {"text": text, "status_code": status_code}

        return {
            "node_results": [
                NodeResult(
                    node_data=self.node_data,
                    status=NodeStatus.SUCCEEDED,
                    inputs=_inputs_dict,
                    outputs=outputs,
                    latency=(time.perf_counter() - start_at),
                )
            ]
        }
