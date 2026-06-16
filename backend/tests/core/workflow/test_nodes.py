"""单节点行为测试：必填校验、jinja2 沙箱、code 沙箱、http SSRF/截断、变量提取。"""
import pytest

from internal.core.workflow.entities.variable_entity import VariableEntity
from internal.core.workflow.nodes.code.code_executor import execute_code, validate_code
from internal.core.workflow.nodes.code.code_node import CodeNode
from internal.core.workflow.nodes.code.code_entity import CodeNodeData
from internal.core.workflow.nodes.http_request.http_request_node import HttpRequestNode
from internal.core.workflow.nodes.http_request.http_request_entity import HttpRequestNodeData
from internal.core.workflow.nodes.start.start_node import StartNode
from internal.core.workflow.nodes.start.start_entity import StartNodeData
from internal.core.workflow.utils.helper import extract_variables_from_state, render_template_sandboxed
from internal.exception import FailException, ForbiddenException

from .graph_factory import input_var, literal_var, nid


def empty_state(inputs=None):
    return {"inputs": inputs or {}, "outputs": {}, "node_results": []}


class TestStartNode:
    def test_required_input_missing(self):
        node = StartNode(node_data=StartNodeData(
            id=nid(), node_type="start", title="开始",
            inputs=[input_var("name", required=True)],
        ))
        with pytest.raises(FailException, match="必填"):
            node.invoke(empty_state())

    def test_optional_input_gets_default(self):
        node = StartNode(node_data=StartNodeData(
            id=nid(), node_type="start", title="开始",
            inputs=[input_var("name", required=False)],
        ))
        result = node.invoke(empty_state())
        assert result["node_results"][0].outputs == {"name": ""}


class TestTemplateSandbox:
    def test_normal_render(self):
        assert render_template_sandboxed("你好，{{ name }}", {"name": "世界"}) == "你好，世界"

    def test_ssti_blocked(self):
        # 沙箱必须拦截 __class__ 属性逃逸链
        with pytest.raises(FailException):
            render_template_sandboxed("{{ ''.__class__.__mro__ }}", {})


class TestCodeSandbox:
    def test_normal_main(self):
        result = execute_code("def main(params):\n    return {'x': params['a'] + 1}\n", {"a": 1})
        assert result == {"x": 2}

    def test_import_rejected(self):
        with pytest.raises(ValueError, match="import"):
            validate_code("def main(params):\n    import os\n    return {}\n")

    def test_dunder_attribute_rejected(self):
        with pytest.raises(ValueError, match="双下划线"):
            validate_code("def main(params):\n    return {'x': ''.__class__}\n")

    def test_blocked_builtin_rejected(self):
        with pytest.raises(ValueError):
            validate_code("def main(params):\n    return {'x': eval('1')}\n")

    def test_extra_statement_rejected(self):
        with pytest.raises(ValueError):
            validate_code("x = 1\ndef main(params):\n    return {}\n")

    def test_open_unavailable_at_runtime(self):
        # AST 拦不到的间接调用，受限 builtins 兜底（open 不在白名单）
        code = "def main(params):\n    f = [abs, len][0]\n    return {'ok': 1}\n"
        assert execute_code(code, {}) == {"ok": 1}

    def test_timeout_killed(self):
        code = "def main(params):\n    while True:\n        pass\n"
        with pytest.raises(ValueError, match="超时"):
            execute_code(code, {}, timeout_seconds=1)

    def test_output_size_capped(self):
        code = "def main(params):\n    return {'x': 'a' * 100000}\n"
        with pytest.raises(ValueError, match="上限"):
            execute_code(code, {}, max_output_bytes=1024)

    def test_non_dict_return_rejected(self):
        with pytest.raises(ValueError, match="字典"):
            execute_code("def main(params):\n    return 1\n", {})


class TestCodeNode:
    def _node(self, is_admin: bool):
        return CodeNode(
            node_data=CodeNodeData(
                id=nid(), node_type="code", title="代码",
                code="def main(params):\n    return {}\n",
            ),
            is_admin=is_admin,
        )

    def test_non_admin_forbidden(self):
        with pytest.raises(ForbiddenException):
            self._node(is_admin=False).invoke(empty_state())

    def test_admin_passes(self):
        result = self._node(is_admin=True).invoke(empty_state())
        assert result["node_results"][0].outputs == {}


class _FakeResponse:
    def __init__(self, body: bytes = b"hello", status_code: int = 200):
        self._body = body
        self.status_code = status_code
        self.encoding = "utf-8"

    def iter_content(self, chunk_size=8192):
        for i in range(0, len(self._body), chunk_size):
            yield self._body[i:i + chunk_size]

    def close(self):
        pass


class TestHttpRequestNode:
    def _node(self, url="http://example.com/api"):
        return HttpRequestNode(node_data=HttpRequestNodeData(
            id=nid(), node_type="http_request", title="HTTP请求", url=url,
        ))

    def test_internal_address_rejected(self):
        # 真实走 safe_request 的 SSRF 校验：环回地址必须被拒
        node = self._node(url="http://127.0.0.1/admin")
        with pytest.raises(FailException, match="不安全"):
            node.invoke(empty_state())

    def test_response_truncated(self, monkeypatch):
        from internal.core.workflow.nodes.http_request import http_request_node as mod

        monkeypatch.setenv("WORKFLOW_HTTP_MAX_RESPONSE_BYTES", "10")
        monkeypatch.setattr(mod, "safe_request", lambda *a, **kw: _FakeResponse(b"x" * 100))
        result = self._node().invoke(empty_state())
        outputs = result["node_results"][0].outputs
        assert outputs["status_code"] == 200
        assert "已截断" in outputs["text"]
        assert outputs["text"].startswith("x" * 10)

    def test_normal_response(self, monkeypatch):
        from internal.core.workflow.nodes.http_request import http_request_node as mod

        monkeypatch.setattr(mod, "safe_request", lambda *a, **kw: _FakeResponse(b"ok-body", 201))
        outputs = self._node().invoke(empty_state())["node_results"][0].outputs
        assert outputs == {"text": "ok-body", "status_code": 201}


class TestExtractVariables:
    def test_literal_and_ref(self):
        from internal.core.workflow.entities.node_entity import NodeResult, NodeStatus
        from internal.core.workflow.nodes.start.start_entity import StartNodeData

        start_id = nid()
        start_data = StartNodeData(id=start_id, node_type="start", title="开始")
        state = {
            "inputs": {},
            "outputs": {},
            "node_results": [NodeResult(
                node_data=start_data, status=NodeStatus.SUCCEEDED,
                inputs={}, outputs={"city": "北京"},
            )],
        }
        variables = [
            VariableEntity.model_validate(literal_var("count", "3", var_type="int")),
            VariableEntity.model_validate({
                "name": "city", "type": "string",
                "value": {"type": "ref", "content": {"ref_node_id": start_id, "ref_var_name": "city"}},
            }),
        ]
        result = extract_variables_from_state(variables, state)
        assert result == {"count": 3, "city": "北京"}
