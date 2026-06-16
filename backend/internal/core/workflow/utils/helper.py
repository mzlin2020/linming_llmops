"""工作流运行时通用工具：变量提取、配置读取、沙箱模板渲染。"""
from typing import Any

from jinja2.sandbox import SandboxedEnvironment

from internal.core.workflow.entities.variable_entity import (
    VARIABLE_TYPE_DEFAULT_VALUE_MAP,
    VARIABLE_TYPE_MAP,
    VariableEntity,
    VariableValueType,
)
from internal.core.workflow.entities.workflow_entity import WorkflowState
from internal.core.workflow.utils.config_read import get_config_int  # noqa: F401  保持既有导入路径可用
from internal.exception import FailException

# 共享的 jinja2 沙箱环境：拦截 __class__ / __subclasses__ 等属性逃逸（SSTI），
# llm prompt 与 template_transform 模板都走它，不允许裸 Template。
_SANDBOX_ENV = SandboxedEnvironment()

# 模板渲染结果长度上限（字符），防异常模板撑爆内存/上下文
TEMPLATE_RENDER_MAX_LENGTH = 64 * 1024


def render_template_sandboxed(template: str, inputs: dict[str, Any]) -> str:
    """沙箱渲染 jinja2 模板；不安全表达式（SecurityError）转业务异常。"""
    try:
        rendered = _SANDBOX_ENV.from_string(template or "").render(**inputs)
    except FailException:
        raise
    except Exception as e:
        # SecurityError / TemplateSyntaxError / UndefinedError 等统一转业务异常，避免吞细节
        raise FailException(message=f"模板渲染失败：{type(e).__name__}: {str(e)[:200]}")
    return rendered[:TEMPLATE_RENDER_MAX_LENGTH]


def extract_variables_from_state(variables: list[VariableEntity], state: WorkflowState) -> dict[str, Any]:
    """从黑板状态中提取变量映射：literal 直转，ref/generated 从前驱节点结果取值并强转类型。"""
    variables_dict = {}

    for variable in variables:
        variable_type_cls = VARIABLE_TYPE_MAP.get(variable.type)

        if variable.value.type == VariableValueType.LITERAL:
            variables_dict[variable.name] = variable_type_cls(variable.value.content)
        else:
            for node_result in state["node_results"]:
                if (
                    isinstance(variable.value.content, VariableEntity.Value.Content)
                    and node_result.node_data.id == variable.value.content.ref_node_id
                ):
                    variables_dict[variable.name] = variable_type_cls(
                        node_result.outputs.get(
                            variable.value.content.ref_var_name,
                            VARIABLE_TYPE_DEFAULT_VALUE_MAP.get(variable.type),
                        )
                    )
    return variables_dict
