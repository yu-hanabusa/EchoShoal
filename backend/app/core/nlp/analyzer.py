"""日本語テキスト解析パイプライン（GiNZA + spaCy ベース）.

シナリオのテキストから以下を抽出する:
- 組織名（企業名、省庁名）
- 技術名（プログラミング言語、フレームワーク、クラウドサービス等）
- 制度・政策名
- 数値表現（人数、金額、割合等）
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# GiNZA / spaCy はオプショナル依存
try:
    import spacy
    _NLP_AVAILABLE = True
except ImportError:
    _NLP_AVAILABLE = False


@dataclass
class ExtractedEntity:
    """抽出されたエンティティ."""
    text: str
    label: str       # ORGANIZATION, TECHNOLOGY, POLICY, QUANTITY, etc.
    start: int = 0
    end: int = 0


@dataclass
class AnalysisResult:
    """テキスト解析の結果."""
    entities: list[ExtractedEntity] = field(default_factory=list)
    organizations: list[str] = field(default_factory=list)
    technologies: list[str] = field(default_factory=list)
    policies: list[str] = field(default_factory=list)
    quantities: list[str] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)


# IT業界の技術辞書（GiNZAの固有表現認識を補完するルールベース辞書）
_TECH_PATTERNS = {
    # プログラミング言語
    r"\b(Python|Go|Java|PHP|Ruby|Rust|C\+\+|C#|TypeScript|JavaScript|Kotlin|Swift|COBOL|VB\.NET)\b",
    # フレームワーク・ライブラリ
    r"\b(React|Vue\.js|Angular|Next\.js|FastAPI|Django|Spring|Rails|Flutter|React Native)\b",
    # クラウド・インフラ
    r"\b(AWS|GCP|Azure|Kubernetes|Docker|Terraform|Ansible)\b",
    # AI・ML（日本語混在のため \b を使わない）
    r"(?:PyTorch|TensorFlow|(?<![A-Za-z])LLM(?![A-Za-z])|ChatGPT|GPT-4|(?<![A-Za-z])Claude(?![A-Za-z])|(?<![A-Za-z])Gemini(?![A-Za-z])|生成AI|機械学習|深層学習)",
    # データベース
    r"\b(PostgreSQL|MySQL|MongoDB|Redis|Neo4j|DynamoDB|BigQuery)\b",
    # ERP・業務系
    r"\b(SAP|Oracle ERP|Salesforce|ServiceNow)\b",
}

# 政策・制度パターン
_POLICY_PATTERNS = {
    r"(DX推進法|デジタル改革|電子帳簿保存法|インボイス制度|マイナンバー|IT基本法)",
    r"(働き方改革|2025年の崖|2030年問題|IT人材白書|デジタル庁)",
    r"(AI規制|個人情報保護法|サイバーセキュリティ基本法|特定技能ビザ)",
}

_COMPILED_TECH = [re.compile(p) for p in _TECH_PATTERNS]
_COMPILED_POLICY = [re.compile(p) for p in _POLICY_PATTERNS]


class JapaneseAnalyzer:
    """日本語テキストを解析してエンティティを抽出する."""

    def __init__(self):
        self._nlp = None

    def _load_model(self):
        """GiNZA モデルを遅延ロードする."""
        if self._nlp is not None:
            return
        if not _NLP_AVAILABLE:
            logger.warning("spaCy/GiNZA が未インストールのためルールベース解析のみ利用可能です")
            return
        try:
            self._nlp = spacy.load("ja_ginza")
            logger.info("GiNZA モデルをロードしました")
        except OSError:
            logger.warning("ja_ginza モデルが見つかりません。ルールベース解析のみ利用可能です")

    def analyze(self, text: str) -> AnalysisResult:
        """テキストを解析し、エンティティを抽出する."""
        self._load_model()

        result = AnalysisResult()

        # ルールベース: 技術名抽出
        for pattern in _COMPILED_TECH:
            for match in pattern.finditer(text):
                entity = ExtractedEntity(
                    text=match.group(),
                    label="TECHNOLOGY",
                    start=match.start(),
                    end=match.end(),
                )
                result.entities.append(entity)
                if match.group() not in result.technologies:
                    result.technologies.append(match.group())

        # ルールベース: 政策名抽出
        for pattern in _COMPILED_POLICY:
            for match in pattern.finditer(text):
                entity = ExtractedEntity(
                    text=match.group(),
                    label="POLICY",
                    start=match.start(),
                    end=match.end(),
                )
                result.entities.append(entity)
                if match.group() not in result.policies:
                    result.policies.append(match.group())

        # GiNZA NER: 組織名・数量・その他の固有表現
        if self._nlp is not None:
            doc = self._nlp(text)
            for ent in doc.ents:
                label = _map_ginza_label(ent.label_)
                entity = ExtractedEntity(
                    text=ent.text,
                    label=label,
                    start=ent.start_char,
                    end=ent.end_char,
                )
                result.entities.append(entity)

                if label == "ORGANIZATION" and ent.text not in result.organizations:
                    result.organizations.append(ent.text)
                elif label == "QUANTITY" and ent.text not in result.quantities:
                    result.quantities.append(ent.text)

            # キーワード抽出（名詞句）
            for chunk in doc.noun_chunks:
                if len(chunk.text) >= 2 and chunk.text not in result.keywords:
                    result.keywords.append(chunk.text)

        return result


def _map_ginza_label(ginza_label: str) -> str:
    """GiNZA の固有表現ラベルを内部ラベルにマッピング."""
    mapping = {
        "ORG": "ORGANIZATION",
        "PERSON": "PERSON",
        "GPE": "LOCATION",
        "LOC": "LOCATION",
        "DATE": "DATE",
        "TIME": "TIME",
        "MONEY": "QUANTITY",
        "PERCENT": "QUANTITY",
        "QUANTITY": "QUANTITY",
        "CARDINAL": "QUANTITY",
        "PRODUCT": "TECHNOLOGY",
        "EVENT": "EVENT",
        "LAW": "POLICY",
        "NORP": "ORGANIZATION",
    }
    return mapping.get(ginza_label, "OTHER")
