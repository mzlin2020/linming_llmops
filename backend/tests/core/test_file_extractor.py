"""file_extractor：按扩展名解析为 LangChain Document（txt/md/csv/xlsx 本机可跑；pdf/docx 交 CI）。"""
import pytest

from internal.core.file_extractor import SUPPORTED_EXTENSIONS, is_supported, load, load_text


def test_is_supported_and_extensions():
    assert is_supported("txt") and is_supported("PDF") and is_supported(".docx")
    assert not is_supported("zip")
    assert {"txt", "md", "markdown", "csv", "pdf", "docx", "xlsx"} == set(SUPPORTED_EXTENSIONS)


def test_load_txt(tmp_path):
    p = tmp_path / "a.txt"
    p.write_text("hello\nworld", encoding="utf-8")
    docs = load(str(p), "txt")
    assert docs and "hello" in docs[0].page_content


def test_load_text_md(tmp_path):
    p = tmp_path / "a.md"
    p.write_text("# 标题\n正文内容", encoding="utf-8")
    text = load_text(str(p), "md")
    assert "正文内容" in text


def test_load_csv(tmp_path):
    p = tmp_path / "a.csv"
    p.write_text("name,age\nalice,30\nbob,25\n", encoding="utf-8")
    text = load_text(str(p), "csv")
    assert "alice" in text and "bob" in text


def test_load_xlsx(tmp_path):
    import openpyxl

    p = tmp_path / "a.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["name", "city"])
    ws.append(["alice", "shanghai"])
    wb.save(str(p))
    docs = load(str(p), "xlsx")
    assert docs and "alice" in docs[0].page_content and "shanghai" in docs[0].page_content


def test_unsupported_ext(tmp_path):
    p = tmp_path / "a.zip"
    p.write_bytes(b"x")
    with pytest.raises(ValueError):
        load(str(p), "zip")


def test_missing_file():
    with pytest.raises(FileNotFoundError):
        load("/no/such/file.txt", "txt")
