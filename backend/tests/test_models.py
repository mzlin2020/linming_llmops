"""Phase 2 模型层单测：建表完整性 / 默认值 / 级联 / 认证解耦回归。

不依赖任何 service / handler；纯 ORM + 迁移后表结构。
本机用文件型 SQLite 代跑（conftest 开了 FK pragma 使 CASCADE 生效）；CI 在真实 MySQL 复跑。
"""


# --------------------------------------------------------------------------- #
# 元数据 / 解耦回归（无需 DB 行，只看 db.metadata）
# --------------------------------------------------------------------------- #
def test_metadata_has_account_and_25_ai_tables(app):
    from internal.extension.database_extension import db

    tables = set(db.metadata.tables)
    assert "account" in tables
    ai_tables = {t for t in tables if t.startswith("ai_")}
    assert len(ai_tables) == 25, sorted(ai_tables)
    for expected in (
        "ai_app", "ai_app_config", "ai_app_config_version", "ai_public_app",
        "ai_conversation", "ai_message", "ai_message_agent_thought",
        "ai_dataset", "ai_document", "ai_segment",
        "ai_keyword_table", "ai_dataset_query", "ai_process_rule",
        "ai_api_tool_provider", "ai_api_tool", "ai_public_plugin",
        "ai_api_key", "ai_end_user", "ai_upload_file", "ai_image",
        "ai_llm_provider", "ai_llm_model", "ai_llm_channel",
        "ai_workflow", "ai_workflow_result",
    ):
        assert expected in tables


def test_no_auth_mirror_tables(app):
    """User/Role/Permission 镜像表已彻底移除——空库可自举的前提。"""
    from internal.extension.database_extension import db

    forbidden = {"user", "users", "roles", "permissions", "user_roles", "role_permissions"}
    assert not (forbidden & set(db.metadata.tables))


def test_no_foreign_key_to_user_or_account(app):
    """认证解耦铁律：任一 ai_* 表都不得有指向 user/account 的外键。"""
    from internal.extension.database_extension import db

    offenders = []
    for tname, tbl in db.metadata.tables.items():
        if not tname.startswith("ai_"):
            continue
        for fk in tbl.foreign_keys:
            target = fk.column.table.name
            if target in ("user", "users", "account", "roles", "permissions"):
                offenders.append((tname, fk.parent.name, target))
    assert offenders == [], offenders


def test_inter_ai_foreign_keys_preserved(app):
    """仅切了 user 耦合：业务表之间的外键（级联）须原样保留。"""
    from internal.extension.database_extension import db

    md = db.metadata.tables

    def fk_targets(table_name):
        return {fk.column.table.name for fk in md[table_name].foreign_keys}

    assert "ai_app" in fk_targets("ai_app_config")
    assert "ai_app" in fk_targets("ai_app_config_version")
    assert "ai_app" in fk_targets("ai_conversation")
    assert "ai_conversation" in fk_targets("ai_message")
    assert "ai_dataset" in fk_targets("ai_document")
    assert "ai_document" in fk_targets("ai_segment")
    assert "ai_api_tool_provider" in fk_targets("ai_api_tool")
    assert "ai_llm_provider" in fk_targets("ai_llm_model")
    assert "ai_llm_provider" in fk_targets("ai_llm_channel")
    assert "ai_workflow" in fk_targets("ai_workflow_result")


# --------------------------------------------------------------------------- #
# 默认值（建仅必填字段的行，提交后回读默认）
# --------------------------------------------------------------------------- #
def test_app_config_defaults(app_context, db_tables):
    from internal.extension.database_extension import db
    from internal.model import App, AppConfig

    app_row = App(name="t", user_id=1)
    db.session.add(app_row)
    db.session.flush()
    cfg = AppConfig(app_id=app_row.id)
    db.session.add(cfg)
    db.session.commit()
    db.session.refresh(cfg)

    assert cfg.model_config == {}
    assert cfg.dialog_round == 3
    assert cfg.preset_prompt == ""
    assert cfg.tools == []
    assert cfg.long_term_memory == {"enable": False}
    assert cfg.suggested_after_answer == {"enable": True}

    db.session.delete(app_row)  # 级联清 cfg
    db.session.commit()


def test_message_defaults(app_context, db_tables):
    from internal.extension.database_extension import db
    from internal.model import App, Conversation, Message

    app_row = App(name="t", user_id=1)
    db.session.add(app_row)
    db.session.flush()
    conv = Conversation(app_id=app_row.id, user_id=1, created_by=1)
    db.session.add(conv)
    db.session.flush()
    msg = Message(app_id=app_row.id, conversation_id=conv.id, created_by=1)
    db.session.add(msg)
    db.session.commit()
    db.session.refresh(msg)

    assert msg.query == ""
    assert msg.answer == ""
    assert msg.image_urls == []
    assert msg.status == "normal"
    assert msg.is_deleted is False
    assert int(msg.total_token_count) == 0

    db.session.delete(app_row)  # 级联清 conv → msg
    db.session.commit()


# --------------------------------------------------------------------------- #
# 级联删除（DB ON DELETE CASCADE + ORM relationship）
# --------------------------------------------------------------------------- #
def test_dataset_cascade_deletes_documents_and_segments(app_context, db_tables):
    from internal.extension.database_extension import db
    from internal.model import Dataset, Document, Segment

    ds = Dataset(user_id=1, name="kb")
    db.session.add(ds)
    db.session.flush()
    doc = Document(user_id=1, dataset_id=ds.id, name="d")
    db.session.add(doc)
    db.session.flush()
    seg = Segment(user_id=1, dataset_id=ds.id, document_id=doc.id)
    db.session.add(seg)
    db.session.commit()
    doc_id, seg_id = doc.id, seg.id

    db.session.delete(ds)
    db.session.commit()

    assert db.session.get(Document, doc_id) is None
    assert db.session.get(Segment, seg_id) is None


def test_app_cascade_deletes_configs_and_conversations(app_context, db_tables):
    from internal.extension.database_extension import db
    from internal.model import App, AppConfig, AppConfigVersion, Conversation, Message

    app_row = App(name="t", user_id=1)
    db.session.add(app_row)
    db.session.flush()
    cfg = AppConfig(app_id=app_row.id)
    ver = AppConfigVersion(app_id=app_row.id)
    conv = Conversation(app_id=app_row.id, user_id=1, created_by=1)
    db.session.add_all([cfg, ver, conv])
    db.session.flush()
    msg = Message(app_id=app_row.id, conversation_id=conv.id, created_by=1)
    db.session.add(msg)
    db.session.commit()
    ids = (cfg.id, ver.id, conv.id, msg.id)

    db.session.delete(app_row)
    db.session.commit()

    assert db.session.get(AppConfig, ids[0]) is None
    assert db.session.get(AppConfigVersion, ids[1]) is None
    assert db.session.get(Conversation, ids[2]) is None
    assert db.session.get(Message, ids[3]) is None


def test_llm_provider_cascade_deletes_models_and_channels(app_context, db_tables):
    from internal.extension.database_extension import db
    from internal.model import LlmProvider, LlmModel, LlmChannel

    prov = LlmProvider(name="openai")
    db.session.add(prov)
    db.session.flush()
    m = LlmModel(provider_id=prov.id, model_name="gpt-x")
    ch = LlmChannel(provider_id=prov.id, name="c1")
    db.session.add_all([m, ch])
    db.session.commit()
    m_id, ch_id = m.id, ch.id

    db.session.delete(prov)
    db.session.commit()

    assert db.session.get(LlmModel, m_id) is None
    assert db.session.get(LlmChannel, ch_id) is None
