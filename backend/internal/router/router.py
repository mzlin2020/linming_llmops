from dataclasses import dataclass

from flask import Blueprint, Flask
from injector import inject

from internal.handler import (
    AccountHandler,
    AIHandler,
    ApiKeyHandler,
    ApiToolHandler,
    AppHandler,
    AssistantAgentHandler,
    AuthHandler,
    BuiltinToolHandler,
    ConversationHandler,
    DatasetHandler,
    DocumentHandler,
    LanguageModelHandler,
    LlmAdminHandler,
    OpenAPIHandler,
    PingHandler,
    SegmentHandler,
    StatsHandler,
    UploadFileHandler,
)


@inject
@dataclass
class Router:
    ping_handler: PingHandler
    auth_handler: AuthHandler
    account_handler: AccountHandler
    upload_file_handler: UploadFileHandler
    dataset_handler: DatasetHandler
    document_handler: DocumentHandler
    segment_handler: SegmentHandler
    app_handler: AppHandler
    conversation_handler: ConversationHandler
    ai_handler: AIHandler
    assistant_agent_handler: AssistantAgentHandler
    # 模型目录 / 工具目录 / 统计 / 插件 / 模型管理 / 开放 API（4c）
    api_key_handler: ApiKeyHandler
    language_model_handler: LanguageModelHandler
    builtin_tool_handler: BuiltinToolHandler
    stats_handler: StatsHandler
    api_tool_handler: ApiToolHandler
    llm_admin_handler: LlmAdminHandler
    openapi_handler: OpenAPIHandler

    def register_router(self, app: Flask):
        bp = Blueprint("api", __name__, url_prefix="/api")

        # 健康检查（public）
        bp.add_url_rule("/ping", view_func=self.ping_handler.ping, methods=["GET"])

        # 认证（public）
        bp.add_url_rule("/auth/register", view_func=self.auth_handler.register, methods=["POST"])
        bp.add_url_rule("/auth/login", view_func=self.auth_handler.login, methods=["POST"])
        bp.add_url_rule("/auth/refresh", view_func=self.auth_handler.refresh, methods=["POST"])
        bp.add_url_rule("/auth/logout", view_func=self.auth_handler.logout, methods=["POST"])

        # 账号（需登录）
        bp.add_url_rule("/account/me", view_func=self.account_handler.me, methods=["GET"])

        # ---------- 知识库：文件上传 ----------
        bp.add_url_rule("/upload-files/file",
                        view_func=self.upload_file_handler.upload_file, methods=["POST"])

        # ---------- 知识库：dataset CRUD + 命中测试 + 查询历史 ----------
        bp.add_url_rule("/datasets",
                        view_func=self.dataset_handler.get_datasets_with_page, methods=["GET"])
        bp.add_url_rule("/datasets", endpoint="create_dataset",
                        view_func=self.dataset_handler.create_dataset, methods=["POST"])
        bp.add_url_rule("/datasets/<int:dataset_id>",
                        view_func=self.dataset_handler.get_dataset, methods=["GET"])
        bp.add_url_rule("/datasets/<int:dataset_id>", endpoint="update_dataset",
                        view_func=self.dataset_handler.update_dataset, methods=["POST"])
        bp.add_url_rule("/datasets/<int:dataset_id>/delete",
                        view_func=self.dataset_handler.delete_dataset, methods=["POST"])
        bp.add_url_rule("/datasets/<int:dataset_id>/hit",
                        view_func=self.dataset_handler.hit, methods=["POST"])
        bp.add_url_rule("/datasets/<int:dataset_id>/queries",
                        view_func=self.dataset_handler.get_dataset_queries, methods=["GET"])

        # ---------- 知识库：文档（注意 /documents/batch/<batch> 的 batch 为静态段，与 <int:document_id> 不冲突） ----------
        bp.add_url_rule("/datasets/<int:dataset_id>/documents",
                        view_func=self.document_handler.get_documents_with_page, methods=["GET"])
        bp.add_url_rule("/datasets/<int:dataset_id>/documents", endpoint="create_documents",
                        view_func=self.document_handler.create_documents, methods=["POST"])
        bp.add_url_rule("/datasets/<int:dataset_id>/documents/batch/<string:batch>",
                        view_func=self.document_handler.get_documents_status, methods=["GET"])
        bp.add_url_rule("/datasets/<int:dataset_id>/documents/<int:document_id>",
                        view_func=self.document_handler.get_document, methods=["GET"])
        bp.add_url_rule("/datasets/<int:dataset_id>/documents/<int:document_id>/name",
                        view_func=self.document_handler.update_document_name, methods=["POST"])
        bp.add_url_rule("/datasets/<int:dataset_id>/documents/<int:document_id>/enabled",
                        view_func=self.document_handler.update_document_enabled, methods=["POST"])
        bp.add_url_rule("/datasets/<int:dataset_id>/documents/<int:document_id>/delete",
                        view_func=self.document_handler.delete_document, methods=["POST"])
        bp.add_url_rule("/datasets/<int:dataset_id>/documents/<int:document_id>/re-index",
                        view_func=self.document_handler.reindex_document, methods=["POST"])

        # ---------- 知识库：片段 ----------
        bp.add_url_rule("/datasets/<int:dataset_id>/documents/<int:document_id>/segments",
                        view_func=self.segment_handler.get_segments_with_page, methods=["GET"])
        bp.add_url_rule("/datasets/<int:dataset_id>/documents/<int:document_id>/segments",
                        endpoint="create_segment",
                        view_func=self.segment_handler.create_segment, methods=["POST"])
        bp.add_url_rule("/datasets/<int:dataset_id>/documents/<int:document_id>/segments/<int:segment_id>",
                        view_func=self.segment_handler.get_segment, methods=["GET"])
        bp.add_url_rule("/datasets/<int:dataset_id>/documents/<int:document_id>/segments/<int:segment_id>",
                        endpoint="update_segment",
                        view_func=self.segment_handler.update_segment, methods=["POST"])
        bp.add_url_rule("/datasets/<int:dataset_id>/documents/<int:document_id>/segments/<int:segment_id>/enabled",
                        view_func=self.segment_handler.update_segment_enabled, methods=["POST"])
        bp.add_url_rule("/datasets/<int:dataset_id>/documents/<int:document_id>/segments/<int:segment_id>/delete",
                        view_func=self.segment_handler.delete_segment, methods=["POST"])

        # ---------- 应用：基础 CRUD ----------
        bp.add_url_rule("/apps", view_func=self.app_handler.list_apps, methods=["GET"])
        bp.add_url_rule("/apps", view_func=self.app_handler.create_app, methods=["POST"])
        # /apps/default 为静态段，先于 /<int:app_id> 注册（int 转换器不匹配 'default'，此处仅为清晰）
        bp.add_url_rule("/apps/default", view_func=self.app_handler.default, methods=["GET"])
        bp.add_url_rule("/apps/<int:app_id>", view_func=self.app_handler.get_app, methods=["GET"])
        bp.add_url_rule("/apps/<int:app_id>", view_func=self.app_handler.update_app, methods=["POST"])
        bp.add_url_rule("/apps/<int:app_id>/delete", view_func=self.app_handler.delete_app, methods=["POST"])
        bp.add_url_rule("/apps/<int:app_id>/copy", view_func=self.app_handler.copy_app, methods=["POST"])

        # ---------- 应用：草稿配置 / 发布 / 版本历史 ----------
        bp.add_url_rule("/apps/<int:app_id>/draft-app-config",
                        view_func=self.app_handler.get_draft_app_config, methods=["GET"])
        bp.add_url_rule("/apps/<int:app_id>/draft-app-config", endpoint="update_draft_app_config",
                        view_func=self.app_handler.update_draft_app_config, methods=["POST"])
        bp.add_url_rule("/apps/<int:app_id>/publish",
                        view_func=self.app_handler.publish, methods=["POST"])
        bp.add_url_rule("/apps/<int:app_id>/cancel-publish",
                        view_func=self.app_handler.cancel_publish, methods=["POST"])
        bp.add_url_rule("/apps/<int:app_id>/publish-histories",
                        view_func=self.app_handler.get_publish_histories, methods=["GET"])
        bp.add_url_rule("/apps/<int:app_id>/fallback-history",
                        view_func=self.app_handler.fallback_history, methods=["POST"])
        bp.add_url_rule("/apps/<int:app_id>/published-config",
                        view_func=self.app_handler.get_published_config, methods=["GET"])

        # ---------- 公共应用商店（发布到商店：任意登录用户对自己已发布的应用）----------
        bp.add_url_rule("/apps/<int:app_id>/store-publish",
                        view_func=self.app_handler.publish_app_to_store, methods=["POST"])
        bp.add_url_rule("/app-store",
                        view_func=self.app_handler.get_app_store, methods=["GET"])
        bp.add_url_rule("/app-store/<int:public_id>/add",
                        view_func=self.app_handler.add_store_app_to_me, methods=["POST"])

        # ---------- Chat（调试，读草稿配置；SSE）----------
        bp.add_url_rule("/apps/<int:app_id>/conversations",
                        view_func=self.app_handler.debug_chat, methods=["POST"])
        bp.add_url_rule("/apps/<int:app_id>/conversations/complete",
                        view_func=self.app_handler.complete_chat, methods=["POST"])
        bp.add_url_rule("/apps/<int:app_id>/conversations/tasks/<string:task_id>/stop",
                        view_func=self.app_handler.stop_debug_chat, methods=["POST"])
        bp.add_url_rule("/apps/<int:app_id>/conversations/messages",
                        view_func=self.app_handler.debug_messages, methods=["GET"])
        bp.add_url_rule("/apps/<int:app_id>/conversations/delete-debug-conversation",
                        view_func=self.app_handler.delete_debug_conversation, methods=["POST"])

        # ---------- 与已发布应用对话（读已发布配置；SSE）----------
        bp.add_url_rule("/apps/<int:app_id>/published-conversations",
                        view_func=self.app_handler.published_chat, methods=["POST"])
        bp.add_url_rule("/apps/<int:app_id>/published-conversations/complete",
                        view_func=self.app_handler.published_complete, methods=["POST"])
        bp.add_url_rule("/apps/<int:app_id>/published-conversations/messages",
                        view_func=self.app_handler.published_messages, methods=["GET"])
        bp.add_url_rule("/apps/<int:app_id>/published-conversations/clear",
                        view_func=self.app_handler.clear_published_conversation, methods=["POST"])

        # ---------- 长期记忆 ----------
        bp.add_url_rule("/apps/<int:app_id>/summary",
                        view_func=self.app_handler.get_summary, methods=["GET"])
        bp.add_url_rule("/apps/<int:app_id>/summary",
                        view_func=self.app_handler.update_summary, methods=["POST"])

        # ---------- AI 辅助 ----------
        bp.add_url_rule("/ai/optimize-preset-prompt",
                        view_func=self.ai_handler.optimize_preset_prompt, methods=["POST"])
        bp.add_url_rule("/ai/suggested-opening-questions",
                        view_func=self.ai_handler.suggest_opening_questions, methods=["POST"])
        bp.add_url_rule("/ai/suggested-questions",
                        view_func=self.ai_handler.suggest_questions, methods=["POST"])

        # ---------- 辅助 Agent（单会话；endpoint 加 assistant_agent_ 前缀，避免与 conversation 同名方法撞车）----------
        bp.add_url_rule("/assistant-agent/chat", endpoint="assistant_agent_chat",
                        view_func=self.assistant_agent_handler.chat, methods=["POST"])
        bp.add_url_rule("/assistant-agent/chat/complete", endpoint="assistant_agent_complete",
                        view_func=self.assistant_agent_handler.complete, methods=["POST"])
        bp.add_url_rule("/assistant-agent/chat/<string:task_id>/stop", endpoint="assistant_agent_stop",
                        view_func=self.assistant_agent_handler.stop, methods=["POST"])
        bp.add_url_rule("/assistant-agent/messages", endpoint="assistant_agent_messages",
                        view_func=self.assistant_agent_handler.messages, methods=["GET"])
        bp.add_url_rule("/assistant-agent/delete-conversation", endpoint="assistant_agent_delete_conversation",
                        view_func=self.assistant_agent_handler.delete_conversation, methods=["POST"])

        # ---------- 会话 / 消息 ----------
        bp.add_url_rule("/conversations",
                        view_func=self.conversation_handler.list_conversations, methods=["GET"])
        bp.add_url_rule("/conversations/<int:conversation_id>",
                        view_func=self.conversation_handler.get_conversation, methods=["GET"])
        bp.add_url_rule("/conversations/<int:conversation_id>/name",
                        view_func=self.conversation_handler.get_name, methods=["GET"])
        bp.add_url_rule("/conversations/<int:conversation_id>/name",
                        view_func=self.conversation_handler.update_name, methods=["POST"])
        bp.add_url_rule("/conversations/<int:conversation_id>/is-pinned",
                        view_func=self.conversation_handler.update_is_pinned, methods=["POST"])
        bp.add_url_rule("/conversations/<int:conversation_id>/delete",
                        view_func=self.conversation_handler.delete_conversation, methods=["POST"])
        bp.add_url_rule("/conversations/<int:conversation_id>/messages",
                        view_func=self.conversation_handler.list_messages, methods=["GET"])
        bp.add_url_rule("/conversations/<int:conversation_id>/messages/<int:message_id>/delete",
                        view_func=self.conversation_handler.delete_message, methods=["POST"])

        # ---------- 全站统计（public）----------
        bp.add_url_rule("/stats", view_func=self.stats_handler.get_site_stats, methods=["GET"])

        # ---------- 语言模型目录（只读，需登录；/icon 静态段先于 /<model> 通配）----------
        bp.add_url_rule("/language-models",
                        view_func=self.language_model_handler.list_models, methods=["GET"])
        bp.add_url_rule("/language-models/<string:provider>",
                        view_func=self.language_model_handler.get_provider, methods=["GET"])
        bp.add_url_rule("/language-models/<string:provider>/icon", endpoint="language_model_provider_icon",
                        view_func=self.language_model_handler.get_provider_icon, methods=["GET"])
        bp.add_url_rule("/language-models/<string:provider>/<string:model>",
                        view_func=self.language_model_handler.get_model, methods=["GET"])

        # ---------- 内置工具目录（只读，需登录）----------
        bp.add_url_rule("/builtin-tools",
                        view_func=self.builtin_tool_handler.get_builtin_tools, methods=["GET"])
        bp.add_url_rule("/builtin-tools/categories",
                        view_func=self.builtin_tool_handler.get_categories, methods=["GET"])
        bp.add_url_rule("/builtin-tools/<string:provider>/tools/<string:tool>",
                        view_func=self.builtin_tool_handler.get_provider_tool, methods=["GET"])
        bp.add_url_rule("/builtin-tools/<string:provider>/icon", endpoint="builtin_tool_provider_icon",
                        view_func=self.builtin_tool_handler.get_provider_icon, methods=["GET"])

        # ---------- 自定义 API 工具 / 插件（需登录，user_id 隔离）----------
        bp.add_url_rule("/api-tools",
                        view_func=self.api_tool_handler.get_api_tool_providers_with_page, methods=["GET"])
        bp.add_url_rule("/api-tools", endpoint="create_api_tool_provider",
                        view_func=self.api_tool_handler.create_api_tool_provider, methods=["POST"])
        bp.add_url_rule("/api-tools/validate-openapi-schema",
                        view_func=self.api_tool_handler.validate_openapi_schema, methods=["POST"])
        bp.add_url_rule("/api-tools/<int:provider_id>",
                        view_func=self.api_tool_handler.get_api_tool_provider, methods=["GET"])
        bp.add_url_rule("/api-tools/<int:provider_id>", endpoint="update_api_tool_provider",
                        view_func=self.api_tool_handler.update_api_tool_provider, methods=["POST"])
        bp.add_url_rule("/api-tools/<int:provider_id>/delete",
                        view_func=self.api_tool_handler.delete_api_tool_provider, methods=["POST"])
        bp.add_url_rule("/api-tools/<int:provider_id>/publish",
                        view_func=self.api_tool_handler.publish_api_tool_provider, methods=["POST"])
        bp.add_url_rule("/api-tools/<int:provider_id>/tools/<string:tool_name>",
                        view_func=self.api_tool_handler.get_api_tool, methods=["GET"])
        bp.add_url_rule("/plugin-store",
                        view_func=self.api_tool_handler.get_plugin_store, methods=["GET"])
        bp.add_url_rule("/plugin-store/<int:public_id>/add",
                        view_func=self.api_tool_handler.add_plugin_to_me, methods=["POST"])

        # ---------- 开放 API 密钥（需登录，account 自管自己的密钥）----------
        bp.add_url_rule("/api-keys",
                        view_func=self.api_key_handler.list_keys, methods=["GET"])
        bp.add_url_rule("/api-keys", endpoint="create_api_key",
                        view_func=self.api_key_handler.create_key, methods=["POST"])
        bp.add_url_rule("/api-keys/<int:key_id>",
                        view_func=self.api_key_handler.update_key, methods=["POST"])
        bp.add_url_rule("/api-keys/<int:key_id>/delete",
                        view_func=self.api_key_handler.delete_key, methods=["POST"])

        # ---------- AI 模型目录管理（写入面，ENABLE_LLM_ADMIN 守护；只读目录走 /language-models）----------
        bp.add_url_rule("/admin/llm-protocols",
                        view_func=self.llm_admin_handler.list_protocols, methods=["GET"])
        bp.add_url_rule("/admin/llm-providers",
                        view_func=self.llm_admin_handler.list_providers, methods=["GET"])
        bp.add_url_rule("/admin/llm-providers", endpoint="create_llm_provider",
                        view_func=self.llm_admin_handler.create_provider, methods=["POST"])
        bp.add_url_rule("/admin/llm-providers/<int:provider_id>", endpoint="update_llm_provider",
                        view_func=self.llm_admin_handler.update_provider, methods=["POST"])
        bp.add_url_rule("/admin/llm-providers/<int:provider_id>/delete",
                        view_func=self.llm_admin_handler.delete_provider, methods=["POST"])
        bp.add_url_rule("/admin/llm-providers/<int:provider_id>/models",
                        view_func=self.llm_admin_handler.create_model, methods=["POST"])
        bp.add_url_rule("/admin/llm-providers/<int:provider_id>/channels",
                        view_func=self.llm_admin_handler.list_channels, methods=["GET"])
        bp.add_url_rule("/admin/llm-providers/<int:provider_id>/channels", endpoint="create_llm_channel",
                        view_func=self.llm_admin_handler.create_channel, methods=["POST"])
        bp.add_url_rule("/admin/llm-models/<int:model_id>", endpoint="update_llm_model",
                        view_func=self.llm_admin_handler.update_model, methods=["POST"])
        bp.add_url_rule("/admin/llm-models/<int:model_id>/delete",
                        view_func=self.llm_admin_handler.delete_model, methods=["POST"])
        bp.add_url_rule("/admin/llm-channels/<int:channel_id>", endpoint="update_llm_channel",
                        view_func=self.llm_admin_handler.update_channel, methods=["POST"])
        bp.add_url_rule("/admin/llm-channels/<int:channel_id>/delete",
                        view_func=self.llm_admin_handler.delete_channel, methods=["POST"])
        bp.add_url_rule("/admin/llm-channels/<int:channel_id>/recover",
                        view_func=self.llm_admin_handler.recover_channel, methods=["POST"])

        app.register_blueprint(bp)

        # ---------- 开放 API（独立蓝图 openapi，用 API-Key 鉴权；中间件按 blueprint 分流）----------
        openapi_bp = Blueprint("openapi", __name__, url_prefix="/api/openapi")
        openapi_bp.add_url_rule("/chat", view_func=self.openapi_handler.chat, methods=["POST"])
        openapi_bp.add_url_rule("/app-info", view_func=self.openapi_handler.app_info, methods=["GET"])
        app.register_blueprint(openapi_bp)
