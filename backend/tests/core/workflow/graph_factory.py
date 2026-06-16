"""工作流测试图工厂：拼 nodes/edges dict（与前端编辑器产出的 JSON 同构）。"""
import uuid


def nid() -> str:
    return str(uuid.uuid4())


def make_start_node(node_id=None, inputs=None, title="开始"):
    return {
        "id": node_id or nid(),
        "node_type": "start",
        "title": title,
        "inputs": inputs or [],
    }


def make_end_node(node_id=None, outputs=None, title="结束"):
    return {
        "id": node_id or nid(),
        "node_type": "end",
        "title": title,
        "outputs": outputs or [],
    }


def make_template_node(node_id=None, template="", inputs=None, title="模板转换"):
    return {
        "id": node_id or nid(),
        "node_type": "template_transform",
        "title": title,
        "template": template,
        "inputs": inputs or [],
    }


def make_edge(source_node: dict, target_node: dict):
    return {
        "id": nid(),
        "source": source_node["id"],
        "source_type": source_node["node_type"],
        "target": target_node["id"],
        "target_type": target_node["node_type"],
    }


def ref_var(name, ref_node, ref_var_name, var_type="string", required=True):
    """引用前驱节点输出的变量。"""
    return {
        "name": name,
        "type": var_type,
        "required": required,
        "value": {"type": "ref", "content": {"ref_node_id": ref_node["id"], "ref_var_name": ref_var_name}},
    }


def literal_var(name, content, var_type="string", required=True):
    return {
        "name": name,
        "type": var_type,
        "required": required,
        "value": {"type": "literal", "content": content},
    }


def input_var(name, var_type="string", required=True, description=""):
    """开始节点的输入变量定义。"""
    return {
        "name": name,
        "type": var_type,
        "required": required,
        "description": description,
        "value": {"type": "generated", "content": ""},
    }


def minimal_graph():
    """start(name) → template_transform(你好，{{ name }}) → end(text)。

    不依赖 LLM/网络/DB，是大多数用例的骨架。返回 (nodes, edges, 三个节点 dict)。
    """
    start = make_start_node(inputs=[input_var("name", description="你的名字")])
    template = make_template_node(
        template="你好，{{ name }}",
        inputs=[ref_var("name", start, "name")],
    )
    end = make_end_node(outputs=[ref_var("text", template, "output")])
    nodes = [start, template, end]
    edges = [make_edge(start, template), make_edge(template, end)]
    return nodes, edges, (start, template, end)
