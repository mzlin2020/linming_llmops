"""ApiToolService：自定义 API 工具（插件）服务——CRUD + OpenAPI 解析（按 user_id 归属隔离）+ 公共插件商店。

对外（handler）返回组装好的 dict；对内（编排校验/解析复用）返回 ORM 行（get_owned_tool）。
越权一律抛 NotFoundException（404，不泄露存在性）。

公共插件商店（ai_public_plugin）：任意登录用户可发布**自己的**私有插件（拍平：无管理员概念，
保留 own 归属约束）；发布=把私有 provider 复制成自包含快照，添加=把公共快照复制回当前用户私有表
（provider.source_public_id 记来源，做「是否已添加」去重）。
"""
import json
from dataclasses import dataclass
from typing import Optional

from injector import inject
from sqlalchemy import desc
from sqlalchemy.orm import selectinload

from internal.core.tools.api_tools.entities import OpenAPISchema
from internal.exception import NotFoundException, ValidateErrorException
from internal.extension.database_extension import db
from internal.lib.helper import dedupe_copy_name
from internal.model import Account, ApiTool, ApiToolProvider, PublicPlugin
from internal.schema.api_tool_schema import (
    CreateApiToolReq,
    GetApiToolProvidersWithPageReq,
    UpdateApiToolProviderReq,
)
from pkg.paginator import Paginator

_NAME_MAX = 64  # ai_api_tool_provider.name 列上限


@dataclass
class _CopyReq:
    """复制公共插件到私有表时喂给 _write_provider 的轻量 req（与 CreateApiToolReq 同形）。"""
    name: str
    icon: str
    openapi_schema: str
    headers: list


def _epoch(dt) -> int:
    return int(dt.timestamp()) if dt else 0


def _provider_brief(provider: ApiToolProvider) -> dict:
    return {
        "id": provider.id,
        "name": provider.name,
        "icon": provider.icon,
        "description": provider.description,
        "headers": provider.headers or [],
    }


def _tool_brief(tool: ApiTool) -> dict:
    return {
        "id": tool.id,
        "name": tool.name,
        "description": tool.description,
        # inputs：参数列表去掉内部的 in 字段，供前端渲染
        "inputs": [{k: v for k, v in p.items() if k != "in"} for p in (tool.parameters or [])],
    }


def _provider_with_tools(provider: ApiToolProvider, is_public: bool = False) -> dict:
    return {**_provider_brief(provider),
            "tools": [_tool_brief(t) for t in provider.tools],
            "is_public": is_public,  # 该私有插件是否已上架商店（子查询公共表算出）
            "created_at": _epoch(provider.created_at)}


def _public_plugin_brief(pub: PublicPlugin, added: bool) -> dict:
    """商店列表项：tools 直接用发布时的快照，零解析。added=当前用户是否已添加过。"""
    return {
        "id": pub.id,
        "name": pub.name,
        "icon": pub.icon,
        "description": pub.description,
        "tools": pub.tools or [],
        "added": added,
        "created_at": _epoch(pub.created_at),
    }


@inject
@dataclass
class ApiToolService:
    """自定义 API 插件服务。"""

    # ---------- 对内：编排集成复用（返回 ORM 行，不抛异常） ----------

    def get_owned_tool(self, provider_id: int, tool_name: str, user_id: int) -> Optional[ApiTool]:
        """按 provider_id + tool_name 取归属 user_id 的工具行；不存在/越权返回 None。"""
        return db.session.query(ApiTool).filter(
            ApiTool.provider_id == provider_id,
            ApiTool.name == tool_name,
            ApiTool.user_id == user_id,
        ).one_or_none()

    # ---------- OpenAPI 解析 ----------

    @classmethod
    def parse_openapi_schema(cls, openapi_schema_str: str) -> OpenAPISchema:
        """解析 openapi_schema 字符串，出错抛 422。"""
        try:
            data = json.loads((openapi_schema_str or "").strip())
            if not isinstance(data, dict):
                raise ValueError
        except Exception:
            raise ValidateErrorException(message="传递数据必须符合 OpenAPI 规范的 JSON 字符串")
        return OpenAPISchema(**data)

    # ---------- CRUD ----------

    def create_api_tool(self, req: CreateApiToolReq, user: Account) -> ApiToolProvider:
        return self._write_provider(req, user.id)

    def update_api_tool_provider(
        self, provider_id: int, req: UpdateApiToolProviderReq, user: Account,
    ) -> ApiToolProvider:
        provider = self._get_owned_provider(provider_id, user.id)
        return self._write_provider(req, user.id, provider)

    def delete_api_tool_provider(self, provider_id: int, user: Account) -> None:
        provider = self._get_owned_provider(provider_id, user.id)
        with db.auto_commit():
            # 连带下架其公共条目（若有），避免商店出现孤儿
            db.session.query(PublicPlugin).filter(
                PublicPlugin.source_provider_id == provider.id
            ).delete()
            db.session.delete(provider)  # FK CASCADE 连带删除其下工具

    # ---------- 查询（返回 dict） ----------

    def get_api_tool_providers_with_page(
        self, req: GetApiToolProvidersWithPageReq, user: Account,
    ) -> dict:
        query = db.session.query(ApiToolProvider).filter(ApiToolProvider.user_id == user.id)
        if req.search_word:
            query = query.filter(ApiToolProvider.name.like(f"%{req.search_word}%"))
        paginator = Paginator(page=req.current_page, page_size=req.page_size, total_record=query.count())
        rows = (
            query.options(selectinload(ApiToolProvider.tools))  # 预加载 tools，避免每行 N+1
            .order_by(desc(ApiToolProvider.created_at))
            .offset(paginator.offset)
            .limit(req.page_size)
            .all()
        )
        # 子查询公共表，标记本页哪些 provider 已上架（is_public），私有表不存发布态
        published_ids = self._published_provider_ids([p.id for p in rows])
        paginator.items = [_provider_with_tools(p, p.id in published_ids) for p in rows]
        return paginator.to_dict()

    def get_api_tool_provider(self, provider_id: int, user: Account) -> dict:
        provider = self._get_owned_provider(provider_id, user.id)
        return {
            "id": provider.id,
            "name": provider.name,
            "icon": provider.icon,
            "openapi_schema": provider.openapi_schema,
            "headers": provider.headers or [],
            "created_at": _epoch(provider.created_at),
        }

    def get_api_tool(self, provider_id: int, tool_name: str, user: Account) -> dict:
        tool = db.session.query(ApiTool).filter_by(provider_id=provider_id, name=tool_name).one_or_none()
        if tool is None or tool.user_id != user.id:
            raise NotFoundException(message="该工具不存在")
        return {**_tool_brief(tool), "provider": _provider_brief(tool.provider)}

    # ---------- 公共插件商店 ----------

    def get_plugin_store_with_page(
        self, req: GetApiToolProvidersWithPageReq, user: Account,
    ) -> dict:
        """商店列表：所有已上架公共插件分页（sort 优先、再按发布时间倒序），附「是否已添加」标记。"""
        query = db.session.query(PublicPlugin)
        if req.search_word:
            query = query.filter(PublicPlugin.name.like(f"%{req.search_word}%"))
        paginator = Paginator(page=req.current_page, page_size=req.page_size, total_record=query.count())
        rows = (
            query.order_by(desc(PublicPlugin.sort), desc(PublicPlugin.created_at))
            .offset(paginator.offset)
            .limit(req.page_size)
            .all()
        )
        added_ids = self._added_public_ids(user.id, [p.id for p in rows])
        paginator.items = [_public_plugin_brief(p, p.id in added_ids) for p in rows]
        return paginator.to_dict()

    def set_provider_public(self, provider_id: int, is_public: bool, user: Account) -> None:
        """发布 / 取消发布：任意登录用户可操作**自己的**私有插件（拍平：无管理员概念，保留 own 约束）。
        发布=upsert 公共快照，取消=删除。"""
        provider = self._get_owned_provider(provider_id, user.id)
        with db.auto_commit():
            existing = db.session.query(PublicPlugin).filter(
                PublicPlugin.source_provider_id == provider.id
            ).one_or_none()
            if is_public:
                # 先算 tools 展示快照（触发 provider.tools 懒加载查询）——必须在 add() 之前，
                # 否则 autoflush 会把刚 add 的 PublicPlugin 以 published_by=NULL 抢先 INSERT
                tools_snapshot = [_tool_brief(t) for t in provider.tools]
                if existing is None:
                    existing = PublicPlugin(source_provider_id=provider.id)
                    db.session.add(existing)
                existing.name = provider.name
                existing.icon = provider.icon
                existing.description = provider.description
                existing.openapi_schema = provider.openapi_schema
                existing.headers = provider.headers or []
                existing.tools = tools_snapshot
                existing.published_by = user.id
            elif existing is not None:
                db.session.delete(existing)

    def add_plugin_to_me(self, public_id: int, user: Account) -> ApiToolProvider:
        """把一条公共插件复制到当前用户私有表（复用 _write_provider 解析 + 拆工具）。"""
        pub = db.session.get(PublicPlugin, public_id)
        if pub is None:
            raise NotFoundException(message="该公共插件不存在")
        dup = db.session.query(ApiToolProvider.id).filter(
            ApiToolProvider.user_id == user.id,
            ApiToolProvider.source_public_id == pub.id,
        ).first()
        if dup is not None:
            raise ValidateErrorException(message="你已添加过该插件")
        # _write_provider 内含同名查重，必须先去重算出唯一名再传入
        name = self._dedupe_name(pub.name, user.id)
        req = _CopyReq(name=name, icon=pub.icon, openapi_schema=pub.openapi_schema, headers=pub.headers or [])
        provider = self._write_provider(req, user.id)
        with db.auto_commit():
            provider.source_public_id = pub.id
        return provider

    # ---------- internal ----------

    def _published_provider_ids(self, provider_ids: list) -> set:
        """这些私有 provider 中，哪些已上架商店（按 ai_public_plugin.source_provider_id）。"""
        if not provider_ids:
            return set()
        return {
            row[0]
            for row in db.session.query(PublicPlugin.source_provider_id)
            .filter(PublicPlugin.source_provider_id.in_(provider_ids))
            .all()
        }

    def _added_public_ids(self, user_id: int, public_ids: list) -> set:
        """这些公共插件中，当前用户已添加过哪些（基于私有 provider.source_public_id）。"""
        if not public_ids:
            return set()
        return {
            row[0]
            for row in db.session.query(ApiToolProvider.source_public_id)
            .filter(
                ApiToolProvider.user_id == user_id,
                ApiToolProvider.source_public_id.in_(public_ids),
            )
            .all()
        }

    def _dedupe_name(self, base: str, user_id: int) -> str:
        """在该用户下算出不与现有 provider 重名的名字（共用 dedupe_copy_name 的「-副本」后缀算法）。"""
        existing = {
            row[0]
            for row in db.session.query(ApiToolProvider.name)
            .filter(ApiToolProvider.user_id == user_id)
            .all()
        }
        return dedupe_copy_name(base, existing, _NAME_MAX)

    def _get_owned_provider(self, provider_id: int, user_id: int) -> ApiToolProvider:
        provider = db.session.get(ApiToolProvider, provider_id)
        if provider is None or provider.user_id != user_id:
            raise NotFoundException(message="该工具提供者不存在")
        return provider

    def _write_provider(
        self, req, user_id: int, provider: Optional[ApiToolProvider] = None,
    ) -> ApiToolProvider:
        """新建（provider=None）/ 覆盖式更新工具提供者，共用解析 + 同名查重 + 建表逻辑。"""
        openapi_schema = self.parse_openapi_schema(req.openapi_schema)
        conflict = db.session.query(ApiToolProvider).filter(
            ApiToolProvider.user_id == user_id,
            ApiToolProvider.name == req.name,
        )
        if provider is not None:
            conflict = conflict.filter(ApiToolProvider.id != provider.id)
        if conflict.first():
            raise ValidateErrorException(message=f"该工具提供者名字 {req.name} 已存在")

        with db.auto_commit():
            if provider is None:
                provider = ApiToolProvider(user_id=user_id)
                db.session.add(provider)
            else:
                db.session.query(ApiTool).filter(ApiTool.provider_id == provider.id).delete()
            provider.name = req.name
            provider.icon = req.icon
            provider.headers = req.headers
            provider.description = openapi_schema.description
            provider.openapi_schema = req.openapi_schema
            db.session.flush()
            self._create_tools_from_schema(provider, openapi_schema, user_id)
        db.session.refresh(provider)
        return provider

    @staticmethod
    def _create_tools_from_schema(provider: ApiToolProvider, openapi_schema: OpenAPISchema, user_id: int) -> None:
        for path, path_item in openapi_schema.paths.items():
            for method, method_item in path_item.items():
                db.session.add(ApiTool(
                    user_id=user_id,
                    provider_id=provider.id,
                    name=method_item.get("operationId"),
                    description=method_item.get("description"),
                    url=f"{openapi_schema.server}{path}",
                    method=method,
                    parameters=method_item.get("parameters", []),
                ))
