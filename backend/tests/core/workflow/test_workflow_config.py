"""WorkflowConfig 严格校验全谱测试（纯内存，不触 DB/LLM）。"""
import pytest

from internal.core.workflow.entities.workflow_entity import WorkflowConfig
from internal.exception import ValidateErrorException

from .graph_factory import (
    input_var,
    make_edge,
    make_end_node,
    make_start_node,
    make_template_node,
    minimal_graph,
    ref_var,
)


def build(nodes, edges, **kwargs):
    params = dict(user_id=1, name="wf_test", description="测试工作流", nodes=nodes, edges=edges)
    params.update(kwargs)
    return WorkflowConfig(**params)


class TestWorkflowConfig:
    def test_minimal_graph_passes(self):
        nodes, edges, _ = minimal_graph()
        config = build(nodes, edges)
        assert len(config.nodes) == 3
        assert len(config.edges) == 2

    def test_invalid_name_rejected(self):
        nodes, edges, _ = minimal_graph()
        with pytest.raises(ValidateErrorException):
            build(nodes, edges, name="非法名字")
        with pytest.raises(ValidateErrorException):
            build(nodes, edges, name="1abc")

    def test_empty_description_rejected(self):
        nodes, edges, _ = minimal_graph()
        with pytest.raises(ValidateErrorException):
            build(nodes, edges, description="")

    def test_double_start_rejected(self):
        nodes, edges, (start, template, end) = minimal_graph()
        start2 = make_start_node(title="开始2")
        with pytest.raises(ValidateErrorException):
            build(nodes + [start2], edges + [make_edge(start2, template)])

    def test_cycle_rejected(self):
        # start → a → b → a 形成环
        start = make_start_node(inputs=[input_var("name")])
        a = make_template_node(title="a", template="x")
        b = make_template_node(title="b", template="y")
        end = make_end_node()
        nodes = [start, a, b, end]
        edges = [
            make_edge(start, a),
            make_edge(a, b),
            make_edge(b, a),  # 环
            make_edge(b, end),
        ]
        with pytest.raises(ValidateErrorException):
            build(nodes, edges)

    def test_isolated_node_rejected(self):
        nodes, edges, _ = minimal_graph()
        # 两个孤岛节点互连，与主图不连通
        orphan1 = make_template_node(title="孤岛1", template="x")
        orphan2 = make_template_node(title="孤岛2", template="y")
        with pytest.raises(ValidateErrorException):
            build(nodes + [orphan1, orphan2], edges + [make_edge(orphan1, orphan2)])

    def test_duplicate_node_id_rejected(self):
        nodes, edges, (start, template, end) = minimal_graph()
        dup = make_template_node(node_id=template["id"], title="重复id", template="x")
        with pytest.raises(ValidateErrorException):
            build(nodes + [dup], edges)

    def test_duplicate_title_rejected(self):
        nodes, edges, (start, template, end) = minimal_graph()
        dup = make_template_node(title=template["title"], template="x")
        with pytest.raises(ValidateErrorException):
            build(nodes + [dup], edges + [make_edge(start, dup), make_edge(dup, template)])

    def test_ref_to_non_predecessor_rejected(self):
        # end 引用了一个不是其前驱的节点变量
        start = make_start_node(inputs=[input_var("name")])
        a = make_template_node(title="a", template="x")
        b = make_template_node(title="b", template="y", inputs=[])
        end = make_end_node(outputs=[ref_var("text", b, "output")])
        # b 不在 end 的前驱链上（start → a → end；b 挂在 start → b → a）
        nodes = [start, a, b, end]
        edges = [make_edge(start, a), make_edge(a, end), make_edge(start, b), make_edge(b, a)]
        # 这里 b 实际是 end 的间接前驱（b→a→end），改成真正的非前驱：引用 end 自己
        end_bad = make_end_node(outputs=[{"name": "text", "value": {
            "type": "ref", "content": {"ref_node_id": end["id"], "ref_var_name": "text"},
        }}])
        nodes_bad = [start, a, b, end_bad]
        edges_bad = [make_edge(start, a), make_edge(a, end_bad), make_edge(start, b), make_edge(b, a)]
        with pytest.raises(ValidateErrorException):
            build(nodes_bad, edges_bad)

    def test_ref_to_missing_var_rejected(self):
        nodes, edges, (start, template, end) = minimal_graph()
        end["outputs"] = [ref_var("text", template, "no_such_var")]
        with pytest.raises(ValidateErrorException):
            build(nodes, edges)

    def test_max_nodes_limit(self, monkeypatch):
        monkeypatch.setenv("WORKFLOW_MAX_NODES", "2")
        nodes, edges, _ = minimal_graph()
        with pytest.raises(ValidateErrorException, match="节点数量"):
            WorkflowConfig(user_id=1, name="wf_test", description="d", nodes=nodes, edges=edges)

    def test_code_node_requires_admin(self):
        nodes, edges, (start, template, end) = minimal_graph()
        code = {
            "id": template["id"], "node_type": "code", "title": "代码",
            "code": "def main(params):\n    return params\n",
            "inputs": [ref_var("name", start, "name")],
        }
        nodes2 = [start, code, end]
        end["outputs"] = []
        edges2 = [make_edge(start, code), make_edge(code, end)]
        with pytest.raises(ValidateErrorException, match="管理员"):
            build(nodes2, edges2)
        # 超管可以通过
        config = build(nodes2, edges2, is_admin=True)
        assert len(config.nodes) == 3

    def test_unknown_node_type_rejected(self):
        nodes, edges, _ = minimal_graph()
        nodes[1]["node_type"] = "no_such_type"
        with pytest.raises(ValidateErrorException):
            build(nodes, edges)
