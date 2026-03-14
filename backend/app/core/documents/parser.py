"""文書パーサー: アップロードファイルからテキストを抽出する.

対応形式:
- .txt: UTF-8テキストファイル
- .pdf: pdfplumber によるテキスト抽出
"""

from __future__ import annotations

import logging
from pathlib import PurePosixPath

from app.core.documents.models import ParsedDocument

logger = logging.getLogger(__name__)

ALLOWED_EXTENSIONS = {".txt", ".pdf"}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB


class DocumentParseError(Exception):
    """文書パース時のエラー."""


class DocumentParser:
    """アップロードされたファイルからテキストを抽出する."""

    def parse(self, content: bytes, filename: str, source: str = "") -> ParsedDocument:
        """ファイル形式に応じてテキストを抽出する.

        Args:
            content: ファイルの生バイト
            filename: 元のファイル名
            source: ソース名（省略時はファイル名を使用）

        Returns:
            ParsedDocument: 抽出済みテキストとメタデータ

        Raises:
            DocumentParseError: ファイル形式不正、サイズ超過等
        """
        # ファイル名のサニタイズ（パストラバーサル防止）
        safe_name = PurePosixPath(filename).name
        if not safe_name:
            raise DocumentParseError("無効なファイル名です")

        # 拡張子チェック
        ext = PurePosixPath(safe_name).suffix.lower()
        if ext not in ALLOWED_EXTENSIONS:
            raise DocumentParseError(
                f"未対応のファイル形式です: {ext}（対応: {', '.join(ALLOWED_EXTENSIONS)}）"
            )

        # サイズチェック
        if len(content) > MAX_FILE_SIZE:
            raise DocumentParseError(
                f"ファイルサイズが上限を超えています: {len(content) / 1024 / 1024:.1f}MB "
                f"（上限: {MAX_FILE_SIZE / 1024 / 1024:.0f}MB）"
            )

        if len(content) == 0:
            raise DocumentParseError("ファイルが空です")

        # 形式別のテキスト抽出
        if ext == ".txt":
            text, page_count = self._parse_text(content)
        elif ext == ".pdf":
            text, page_count = self._parse_pdf(content)
        else:
            raise DocumentParseError(f"未対応の形式: {ext}")

        if not text.strip():
            raise DocumentParseError("ファイルからテキストを抽出できませんでした")

        return ParsedDocument(
            filename=safe_name,
            text=text,
            page_count=page_count,
            source=source or safe_name,
        )

    def _parse_text(self, content: bytes) -> tuple[str, int]:
        """テキストファイルからテキストを抽出する."""
        for encoding in ("utf-8", "shift_jis", "euc-jp", "cp932"):
            try:
                text = content.decode(encoding)
                return text, 1
            except (UnicodeDecodeError, ValueError):
                continue
        raise DocumentParseError("テキストのエンコーディングを判定できませんでした")

    def _parse_pdf(self, content: bytes) -> tuple[str, int]:
        """PDFファイルからテキストを抽出する."""
        try:
            import pdfplumber
        except ImportError:
            raise DocumentParseError(
                "PDF解析にはpdfplumberが必要です。"
                "`uv sync --extra docs` でインストールしてください"
            )

        import io

        pages_text: list[str] = []
        try:
            with pdfplumber.open(io.BytesIO(content)) as pdf:
                for page in pdf.pages:
                    text = page.extract_text()
                    if text:
                        pages_text.append(text)
                page_count = len(pdf.pages)
        except Exception as exc:
            raise DocumentParseError(f"PDF解析に失敗しました: {exc}") from exc

        return "\n\n".join(pages_text), page_count
