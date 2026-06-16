"""WorkflowTool 测试：动态 args_schema、惰性编译、端到端 invoke/stream、并行分支合流。"""
from internal.core.workflow import WorkflowConfig, WorkflowTool

from .graph_factory import (
    input_var,
    make_edge,
    make_end_node,
    make_start_node,
    make_template_node,
    minimal_graph,
    ref_var,
)


def build_tool(nodes, edges, **kwargs):
    params = dict(user_id=1, name="wf_test", description="测试工作流", nodes=nodes, edges=edges)
    params.update(kwargs)
    return WorkflowTool(WorkflowConfig(**params))


class TestWorkflowTool:
    def test_args_schema_required_and_optional(self):
        start = make_start_node(inputs=[
            input_var("name", description="名字", required=True),
            input_var("age", var_type="int", required=False),
        ])
        template = make_template_node(template="{{ name }}", inputs=[ref_var("name", start, "name")])
        end = make_end_node(outputs=[ref_var("text", template, "output")])
        tool = build_tool([start, template, end], [make_edge(start, template), make_edge(template, end)])

        fields = tool.args_schema.model_fields
        assert fields["name"].is_required()
        assert not fields["age"].is_required()
        assert fields["age"].default is None
        assert tool.name == "wf_test"

    def test_lazy_compile(self):
        nodes, edges, _ = minimal_graph()
        tool = build_tool(nodes, edges)
        # 构造后未编译
        assert tool._compiled is None
        result = tool._run(name="世界")
        assert result == {"text": "你好，世界"}
        # 首次运行后已编译并缓存
        assert tool._compiled is not None

    def test_stream_yields_per_node(self):
        nodes, edges, _ = minimal_graph()
        tool = build_tool(nodes, edges)
        chunks = list(tool.stream({"name": "世界"}))
        # start / template_transform / end 各一帧
        assert len(chunks) == 3
        node_flags = [list(c.keys())[0] for c in chunks]
        assert node_flags[0].startswith("start_")
        assert node_flags[-1].startswith("end_")
        # 每帧带 node_results
        first = chunks[0][node_flags[0]]
        assert first["node_results"][0].status == "succeeded"

    def test_parallel_branches_merge(self):
        # start → (t1, t2) → end：扇出后在 end 扇入，黑板 reducer 合并两个分支的结果
        start = make_start_node(inputs=[input_var("name")])
        t1 = make_template_node(title="t1", template="A-{{ name }}", inputs=[ref_var("name", start, "name")])
        t2 = make_template_node(title="t2", template="B-{{ name }}", inputs=[ref_var("name", start, "name")])
        end = make_end_node(outputs=[
            ref_var("a", t1, "output"),
            ref_var("b", t2, "output"),
        ])
        nodes = [start, t1, t2, end]
        edges = [
            make_edge(start, t1),
            make_edge(start, t2),
            make_edge(t1, end),
            make_edge(t2, end),
        ]
        tool = build_tool(nodes, edges)
        result = tool._run(name="x")
        assert result == {"a": "A-x", "b": "B-x"}
