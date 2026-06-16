"""全文检索器：jieba 分词 + ai_keyword_table 倒排 + 回表 ai_segment（真实 DB，本机 SQLite 代跑）。"""
from internal.core.retrievers import FullTextRetriever, tokenize_keywords
from internal.core.retrievers import full_text_retriever as ftr


def test_tokenize_keywords_returns_terms():
    kws = tokenize_keywords("我爱自然语言处理技术")
    assert isinstance(kws, list) and len(kws) >= 1


def test_full_text_retriever_hits_by_keyword(app_context, db_tables, monkeypatch):
    from internal.extension.database_extension import db
    from internal.model import Dataset, Document, KeywordTable, Segment

    ds = Dataset(user_id=1, name="kb")
    db.session.add(ds)
    db.session.flush()
    doc = Document(user_id=1, dataset_id=ds.id, name="d")
    db.session.add(doc)
    db.session.flush()
    seg1 = Segment(user_id=1, dataset_id=ds.id, document_id=doc.id, node_id="n1", content="Python 是一门编程语言")
    seg2 = Segment(user_id=1, dataset_id=ds.id, document_id=doc.id, node_id="n2", content="今天天气晴朗")
    db.session.add_all([seg1, seg2])
    db.session.flush()
    kt = KeywordTable(dataset_id=ds.id, keyword_table={"python": [seg1.id], "天气": [seg2.id]})
    db.session.add(kt)
    db.session.commit()
    seg1_id = seg1.id

    # 固定分词，专测倒排合并 + 回表组装（jieba 本身另有用例）。
    monkeypatch.setattr(ftr, "tokenize_keywords", lambda q, topk=10: ["python"])
    retr = FullTextRetriever(dataset_ids=[ds.id], k=4)
    docs = retr.invoke("无关紧要的 query")

    assert len(docs) == 1
    assert docs[0].metadata["segment_id"] == seg1_id
    assert docs[0].metadata["score"] == 0.0
    assert "Python" in docs[0].page_content

    db.session.delete(kt)
    db.session.delete(ds)  # 级联清 doc + segment
    db.session.commit()


def test_full_text_retriever_no_keyword_match(app_context, db_tables, monkeypatch):
    from internal.extension.database_extension import db
    from internal.model import Dataset, KeywordTable

    ds = Dataset(user_id=1, name="kb2")
    db.session.add(ds)
    db.session.flush()
    kt = KeywordTable(dataset_id=ds.id, keyword_table={"python": [1]})
    db.session.add(kt)
    db.session.commit()

    monkeypatch.setattr(ftr, "tokenize_keywords", lambda q, topk=10: ["不存在的词"])
    retr = FullTextRetriever(dataset_ids=[ds.id], k=4)
    assert retr.invoke("q") == []

    db.session.delete(kt)
    db.session.delete(ds)
    db.session.commit()
