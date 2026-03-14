"""Tests for document parser."""

import pytest

from app.core.documents.parser import (
    ALLOWED_EXTENSIONS,
    MAX_FILE_SIZE,
    DocumentParseError,
    DocumentParser,
)


class TestDocumentParser:
    def setup_method(self):
        self.parser = DocumentParser()

    def test_parse_text_utf8(self):
        content = "日本のIT業界ではPythonとAWSの需要が高まっている。".encode("utf-8")
        doc = self.parser.parse(content, "report.txt")
        assert "Python" in doc.text
        assert doc.filename == "report.txt"
        assert doc.page_count == 1

    def test_parse_text_shift_jis(self):
        content = "日本語テスト".encode("shift_jis")
        doc = self.parser.parse(content, "sjis.txt")
        assert "日本語" in doc.text

    def test_parse_text_with_source(self):
        content = b"test content"
        doc = self.parser.parse(content, "file.txt", source="IPA Report")
        assert doc.source == "IPA Report"

    def test_parse_text_default_source(self):
        content = b"test"
        doc = self.parser.parse(content, "file.txt")
        assert doc.source == "file.txt"

    def test_reject_unsupported_extension(self):
        with pytest.raises(DocumentParseError, match="未対応"):
            self.parser.parse(b"content", "file.exe")

    def test_reject_docx(self):
        with pytest.raises(DocumentParseError, match="未対応"):
            self.parser.parse(b"content", "file.docx")

    def test_reject_empty_file(self):
        with pytest.raises(DocumentParseError, match="空"):
            self.parser.parse(b"", "empty.txt")

    def test_reject_oversized_file(self):
        content = b"x" * (MAX_FILE_SIZE + 1)
        with pytest.raises(DocumentParseError, match="上限"):
            self.parser.parse(content, "huge.txt")

    def test_reject_whitespace_only(self):
        with pytest.raises(DocumentParseError, match="テキストを抽出できません"):
            self.parser.parse(b"   \n\n  ", "whitespace.txt")

    def test_sanitize_path_traversal(self):
        content = b"test"
        doc = self.parser.parse(content, "../../etc/passwd.txt")
        assert doc.filename == "passwd.txt"

    def test_reject_empty_filename(self):
        with pytest.raises(DocumentParseError, match="無効"):
            self.parser.parse(b"test", "")

    def test_allowed_extensions(self):
        assert ".txt" in ALLOWED_EXTENSIONS
        assert ".pdf" in ALLOWED_EXTENSIONS
        assert ".exe" not in ALLOWED_EXTENSIONS

    def test_generates_unique_ids(self):
        content = b"test"
        doc1 = self.parser.parse(content, "a.txt")
        doc2 = self.parser.parse(content, "b.txt")
        assert doc1.id != doc2.id

    def test_pdf_without_pdfplumber(self):
        """pdfplumber未インストール時のエラーメッセージ."""
        # 実際のPDFバイトではないのでパースは失敗するはず
        # pdfplumberがインストールされている場合は別のエラーになる
        content = b"not a real pdf"
        try:
            self.parser.parse(content, "test.pdf")
            # pdfplumberがあれば「PDF解析に失敗」エラー
            pytest.fail("Expected DocumentParseError")
        except DocumentParseError as e:
            assert "PDF" in str(e) or "pdfplumber" in str(e)
