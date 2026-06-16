"""草稿配置的序列化与校验：
- tools：校验为合法的 builtin_tool / api_tool 引用列表后落库（接 Agent 运行时）。
- datasets：校验为归属当前用户的知识库 id 列表后落库（接按-app chat 的 dataset_retrieval 工具）。
- workflows：校验为归属当前用户的「已发布」工作流 id 列表后落库（接按-app chat 的 workflow-as-tool）。
- 其余字段做类型与范围校验后原样落库。
"""
from dataclasses import dataclass

from injector import inject

from internal.core.language_model.defaults import resolve_default_provider_model
from internal.core.tools.builtin_tools.providers import BuiltinProviderManager
from internal.entity.workflow_entity import WorkflowStatus
from internal.exception import ValidateErrorException
from internal.extension.database_extension import db
from internal.model import Dataset, Workflow
from internal.model.app import CONFIG_FIELDS
from internal.service.api_tool_service import ApiToolService

# 单个应用关联的工具数量上限（内置 + 自定义合计），与前端工具配置选择器保持同步
_MAX_TOOLS = 10

# 单个应用关联的知识库数量上限，与前端知识库配置选择器保持同步
_MAX_DATASETS = 5

# 单个应用关联的工作流数量上限
_MAX_WORKFLOWS = 5


def _default_model_config() -> dict:
    """缺省模型配置：provider/model 取环境变量默认值（OpenAI 兼容），与 chat 链路同一回落链。"""
    provider, model = resolve_default_provider_model()
    return {"provider": provider, "model": model, "parameters": {}}


def serialize_config(record) -> dict:
    """把一条 AppConfig / AppConfigVersion 行序列化成前端配置字典（14 字段全集）。
    model_config 为空时补默认 provider/model，方便前端模型选择器回显当前生效模型。"""
    data = {field: getattr(record, field) for field in CONFIG_FIELDS}
    mc = dict(data.get("model_config") or {})
    if not mc.get("provider") or not mc.get("model"):
        defaults = _default_model_config()
        mc.setdefault("provider", defaults["provider"])
        mc.setdefault("model", defaults["model"])
    mc.setdefault("parameters", {})
    data["model_config"] = mc
    return data


@inject
@dataclass
class AppConfigService:
    builtin_provider_manager: BuiltinProviderManager
    api_tool_service: ApiToolService

    def get_draft_app_config(self, app) -> dict:
        """取应用草稿配置（展示格式）。"""
        return serialize_config(app.draft_app_config)

    def get_published_config(self, app) -> dict:
        """取应用已发布配置；未发布返回 None。"""
        published = app.app_config
        if published is None:
            return None
        return serialize_config(published)

    def validate_draft_app_config(self, payload: dict, user_id: int = None, is_admin: bool = False) -> dict:
        """校验并规整前端提交的草稿配置，返回只含已知字段的干净 dict（用于原地更新草稿行）。
        - 只接收 CONFIG_FIELDS 中的键，未知键忽略
        - model_config: 必须是 dict，缺 provider/model 时补默认值
        - dialog_round: 0~100 的整数
        - preset_prompt / opening_statement: 字符串
        - opening_questions: 字符串列表（最多 5 条）
        - tools: builtin_tool / api_tool 引用列表（合计 ≤10），api_tool 需归属 user_id
        - workflows/datasets: 归属当前用户的 id 列表
        - 其余 dict 字段原样保留
        """
        cleaned: dict = {}

        if "model_config" in payload:
            mc = payload.get("model_config")
            if not isinstance(mc, dict):
                mc = {}
            defaults = _default_model_config()
            cleaned["model_config"] = {
                "provider": str(mc.get("provider") or defaults["provider"]),
                "model": str(mc.get("model") or defaults["model"]),
                "parameters": mc.get("parameters") if isinstance(mc.get("parameters"), dict) else {},
            }

        if "dialog_round" in payload:
            try:
                dr = int(payload.get("dialog_round"))
            except (TypeError, ValueError):
                dr = 3
            cleaned["dialog_round"] = max(0, min(100, dr))

        if "preset_prompt" in payload:
            cleaned["preset_prompt"] = str(payload.get("preset_prompt") or "")[:8000]

        if "opening_statement" in payload:
            cleaned["opening_statement"] = str(payload.get("opening_statement") or "")[:2000]

        if "opening_questions" in payload:
            oq = payload.get("opening_questions") or []
            if isinstance(oq, list):
                cleaned["opening_questions"] = [str(q)[:200] for q in oq][:5]
            else:
                cleaned["opening_questions"] = []

        if "tools" in payload:
            cleaned["tools"] = self._validate_tools(payload.get("tools"), user_id, is_admin)

        if "datasets" in payload:
            cleaned["datasets"] = self._validate_datasets(payload.get("datasets"), user_id)

        if "workflows" in payload:
            cleaned["workflows"] = self._validate_workflows(payload.get("workflows"), user_id)

        # 其余 dict 型保留字段（开关类）原样保留
        for field in ("retrieval_config", "long_term_memory", "speech_to_text",
                      "text_to_speech", "suggested_after_answer", "review_config"):
            if field in payload and isinstance(payload.get(field), dict):
                cleaned[field] = payload.get(field)

        return cleaned

    def _validate_tools(self, raw, user_id: int = None, is_admin: bool = False) -> list:
        """校验并规整 tools 配置：支持 builtin_tool 与 api_tool，合计 ≤10。
        - builtin_tool：provider/tool 必须真实存在；admin_only 工具仅超管可绑定
        - api_tool：必须归属 user_id 且存在；user_id 缺失（如全局辅助 Agent）时无法校验归属，跳过
        非法 type 的项忽略；存在性/归属校验失败抛 422（前端选择器只会提交合法项）。"""
        if not isinstance(raw, list):
            return []
        cleaned: list = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            tool_type = item.get("type")
            if tool_type == "builtin_tool":
                normalized = self._validate_builtin_tool(item, is_admin)
                if normalized is not None:
                    cleaned.append(normalized)
            elif tool_type == "api_tool":
                normalized = self._validate_api_tool(item, user_id)
                if normalized is not None:
                    cleaned.append(normalized)
            # 其余 type 忽略
        if len(cleaned) > _MAX_TOOLS:
            raise ValidateErrorException(message=f"一个应用最多关联 {_MAX_TOOLS} 个工具")
        return cleaned

    def _validate_datasets(self, raw, user_id: int = None) -> list:
        """校验并规整 datasets 配置：去重保序的知识库 id 列表，合计 ≤_MAX_DATASETS。
        - 只保留归属 user_id 的库（顺手挡掉越权 / 已删除的 id）
        - user_id 缺失（如全局辅助 Agent）时无法校验归属，一律返回 []（辅助 Agent 不接知识库）
        非数字项忽略；数量超限抛 422（前端选择器已限，这是兜底）。"""
        if not isinstance(raw, list) or user_id is None:
            return []
        # 归一化为去重保序的 int id 列表
        ids: list = []
        seen: set = set()
        for x in raw:
            try:
                i = int(x)
            except (TypeError, ValueError):
                continue
            if i not in seen:
                seen.add(i)
                ids.append(i)
        if not ids:
            return []
        # 只保留归属当前用户的库
        owned = {
            row[0]
            for row in db.session.query(Dataset.id)
            .filter(Dataset.id.in_(ids), Dataset.user_id == user_id)
            .all()
        }
        result = [i for i in ids if i in owned]
        if len(result) > _MAX_DATASETS:
            raise ValidateErrorException(message=f"一个应用最多关联 {_MAX_DATASETS} 个知识库")
        return result

    def _validate_workflows(self, raw, user_id: int = None) -> list:
        """校验并规整 workflows 配置：去重保序的工作流 id 列表，合计 ≤_MAX_WORKFLOWS。
        - 只保留「归属 user_id 且已发布」的工作流（取消发布/删除/越权的 id 静默过滤）
        - user_id 缺失（如全局辅助 Agent）时一律返回 []（辅助 Agent 不接工作流）
        非数字项忽略；数量超限抛 422（前端选择器已限，这是兜底）。"""
        if not isinstance(raw, list) or user_id is None:
            return []
        ids: list = []
        seen: set = set()
        for x in raw:
            try:
                i = int(x)
            except (TypeError, ValueError):
                continue
            if i not in seen:
                seen.add(i)
                ids.append(i)
        if not ids:
            return []
        owned = {
            row[0]
            for row in db.session.query(Workflow.id)
            .filter(
                Workflow.id.in_(ids),
                Workflow.user_id == user_id,
                Workflow.status == WorkflowStatus.PUBLISHED.value,
            )
            .all()
        }
        result = [i for i in ids if i in owned]
        if len(result) > _MAX_WORKFLOWS:
            raise ValidateErrorException(message=f"一个应用最多关联 {_MAX_WORKFLOWS} 个工作流")
        return result

    def _validate_builtin_tool(self, item: dict, is_admin: bool = False):
        provider_name = (item.get("provider") or {}).get("name")
        tool_name = (item.get("tool") or {}).get("name")
        if not provider_name or not tool_name:
            raise ValidateErrorException(message="工具配置缺少 provider/tool 名称")
        provider = self.builtin_provider_manager.get_provider(provider_name)
        if provider is None or provider.get_tool_entity(tool_name) is None:
            raise ValidateErrorException(message=f"工具不存在: {provider_name}/{tool_name}")
        # admin_only 工具仅超管可绑定：非超管时静默剔除（返回 None），不抛错——否则保存「从商店复制来、
        # 恰好含该工具」的应用会整体失败。本项目无 admin 概念（is_admin 恒 False），故此类工具一律不绑定。
        if getattr(provider.provider_entity, "admin_only", False) and not is_admin:
            return None
        params = (item.get("tool") or {}).get("params")
        return {
            "type": "builtin_tool",
            "provider": {"name": provider_name},
            "tool": {"name": tool_name, "params": params if isinstance(params, dict) else {}},
        }

    def _validate_api_tool(self, item: dict, user_id: int = None):
        provider_id = (item.get("provider") or {}).get("id")
        tool_name = (item.get("tool") or {}).get("name")
        if not provider_id or not tool_name:
            raise ValidateErrorException(message="自定义工具配置缺少 provider.id/tool.name")
        if user_id is None:
            # 无归属上下文，无法校验归属，跳过自定义工具
            return None
        owned = self.api_tool_service.get_owned_tool(provider_id, tool_name, user_id)
        if owned is None:
            raise ValidateErrorException(message=f"自定义工具不存在或无权访问: {provider_id}/{tool_name}")
        return {
            "type": "api_tool",
            "provider": {"id": owned.provider_id, "name": owned.provider.name},
            "tool": {"id": owned.id, "name": owned.name},
        }
