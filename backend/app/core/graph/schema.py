"""知識グラフのスキーマ定義と初期化.

ノード:
  - Industry: 業界セグメント（SIer, SES, フリーランス等）
  - Company: 企業（SES企業、SIer企業、事業会社等）
  - Skill: 技術スキル（Python, AWS, COBOL 等）
  - SkillCategory: スキルカテゴリ（web_backend, cloud_infra 等）
  - Role: 職種（SE, PG, PM, インフラエンジニア等）
  - Policy: 政策・制度（DX推進法、インボイス制度等）

リレーション:
  - Company -[BELONGS_TO]-> Industry
  - Company -[DEMANDS]-> Skill        {urgency, volume}
  - Company -[EMPLOYS]-> Role          {count, avg_salary}
  - Skill -[CATEGORIZED_AS]-> SkillCategory
  - Skill -[REQUIRES]-> Skill          (前提スキル)
  - Skill -[EVOLVES_INTO]-> Skill      (スキルの進化)
  - Policy -[AFFECTS]-> Industry       {impact_type, magnitude}
  - Policy -[AFFECTS]-> Skill          {impact_type, magnitude}
  - Role -[USES]-> Skill               {proficiency_required}
"""

from __future__ import annotations

import logging
from typing import Any

from app.core.graph.client import GraphClient

logger = logging.getLogger(__name__)

# --- スキーマ制約・インデックス ---

SCHEMA_CONSTRAINTS = [
    "CREATE CONSTRAINT IF NOT EXISTS FOR (i:Industry) REQUIRE i.name IS UNIQUE",
    "CREATE CONSTRAINT IF NOT EXISTS FOR (s:Skill) REQUIRE s.name IS UNIQUE",
    "CREATE CONSTRAINT IF NOT EXISTS FOR (sc:SkillCategory) REQUIRE sc.name IS UNIQUE",
    "CREATE CONSTRAINT IF NOT EXISTS FOR (r:Role) REQUIRE r.name IS UNIQUE",
    "CREATE CONSTRAINT IF NOT EXISTS FOR (c:Company) REQUIRE c.name IS UNIQUE",
    "CREATE CONSTRAINT IF NOT EXISTS FOR (p:Policy) REQUIRE p.name IS UNIQUE",
    "CREATE CONSTRAINT IF NOT EXISTS FOR (sr:StatRecord) REQUIRE sr.name IS UNIQUE",
    "CREATE CONSTRAINT IF NOT EXISTS FOR (a:Agent) REQUIRE a.agent_id IS UNIQUE",
    "CREATE CONSTRAINT IF NOT EXISTS FOR (d:Document) REQUIRE d.doc_id IS UNIQUE",
]

# --- 初期データ ---

SEED_INDUSTRIES = [
    {"name": "sier", "label_ja": "SIer（システムインテグレータ）", "description": "大規模システム開発を受託する元請け企業群"},
    {"name": "ses", "label_ja": "SES（システムエンジニアリングサービス）", "description": "エンジニアを客先常駐で派遣する企業群"},
    {"name": "freelance", "label_ja": "フリーランス", "description": "個人で業務委託契約を結ぶ独立エンジニア"},
    {"name": "web_startup", "label_ja": "Web系スタートアップ", "description": "自社プロダクトを開発するWeb系企業"},
    {"name": "enterprise_it", "label_ja": "事業会社IT部門", "description": "非IT企業の社内IT部門・情報システム部"},
]

SEED_SKILL_CATEGORIES = [
    {"name": "legacy", "label_ja": "レガシー", "skills": ["COBOL", "VB.NET", "メインフレーム", "AS/400"]},
    {"name": "web_frontend", "label_ja": "Webフロントエンド", "skills": ["React", "Vue.js", "TypeScript", "Angular", "Next.js"]},
    {"name": "web_backend", "label_ja": "Webバックエンド", "skills": ["Python", "Go", "Node.js", "Java", "PHP", "Ruby"]},
    {"name": "cloud_infra", "label_ja": "クラウド・インフラ", "skills": ["AWS", "GCP", "Azure", "Kubernetes", "Docker", "Terraform"]},
    {"name": "ai_ml", "label_ja": "AI・機械学習", "skills": ["PyTorch", "TensorFlow", "LLM", "データサイエンス", "MLOps"]},
    {"name": "security", "label_ja": "セキュリティ", "skills": ["ペネトレーションテスト", "SOC運用", "ISMS", "ゼロトラスト"]},
    {"name": "mobile", "label_ja": "モバイル", "skills": ["Swift", "Kotlin", "Flutter", "React Native"]},
    {"name": "erp", "label_ja": "ERP", "skills": ["SAP", "Oracle ERP", "Salesforce", "ServiceNow"]},
]

SEED_ROLES = [
    {"name": "se", "label_ja": "システムエンジニア"},
    {"name": "pg", "label_ja": "プログラマ"},
    {"name": "pm", "label_ja": "プロジェクトマネージャ"},
    {"name": "infra", "label_ja": "インフラエンジニア"},
    {"name": "data_scientist", "label_ja": "データサイエンティスト"},
    {"name": "security_engineer", "label_ja": "セキュリティエンジニア"},
    {"name": "sre", "label_ja": "SRE"},
    {"name": "designer", "label_ja": "UIデザイナー"},
]


async def initialize_schema(client: GraphClient) -> None:
    """スキーマ制約を作成する."""
    for constraint in SCHEMA_CONSTRAINTS:
        await client.execute_write(constraint)
    logger.info("知識グラフスキーマを初期化しました")


async def seed_initial_data(client: GraphClient) -> None:
    """初期データを投入する（冪等）."""
    # 業界
    for ind in SEED_INDUSTRIES:
        await client.execute_write(
            "MERGE (i:Industry {name: $name}) "
            "SET i.label_ja = $label_ja, i.description = $description",
            ind,
        )

    # スキルカテゴリ + スキル
    for cat in SEED_SKILL_CATEGORIES:
        await client.execute_write(
            "MERGE (sc:SkillCategory {name: $name}) SET sc.label_ja = $label_ja",
            {"name": cat["name"], "label_ja": cat["label_ja"]},
        )
        for skill_name in cat["skills"]:
            await client.execute_write(
                "MERGE (s:Skill {name: $skill_name}) "
                "WITH s "
                "MATCH (sc:SkillCategory {name: $cat_name}) "
                "MERGE (s)-[:CATEGORIZED_AS]->(sc)",
                {"skill_name": skill_name, "cat_name": cat["name"]},
            )

    # 職種
    for role in SEED_ROLES:
        await client.execute_write(
            "MERGE (r:Role {name: $name}) SET r.label_ja = $label_ja",
            role,
        )

    logger.info("初期データを投入しました")


class KnowledgeGraphRepository:
    """知識グラフへの読み書きを行うリポジトリ."""

    def __init__(self, client: GraphClient):
        self.client = client

    # --- スキル関連 ---

    async def get_skills_by_category(self, category: str) -> list[dict[str, Any]]:
        """カテゴリに属するスキル一覧を取得."""
        return await self.client.execute_read(
            "MATCH (s:Skill)-[:CATEGORIZED_AS]->(sc:SkillCategory {name: $cat}) "
            "RETURN s.name AS name",
            {"cat": category},
        )

    async def get_skill_relations(self, skill_name: str) -> dict[str, Any]:
        """スキルの前提・進化先・カテゴリを取得."""
        requires = await self.client.execute_read(
            "MATCH (s:Skill {name: $name})-[:REQUIRES]->(req:Skill) "
            "RETURN req.name AS name",
            {"name": skill_name},
        )
        evolves = await self.client.execute_read(
            "MATCH (s:Skill {name: $name})-[:EVOLVES_INTO]->(evo:Skill) "
            "RETURN evo.name AS name",
            {"name": skill_name},
        )
        category = await self.client.execute_read(
            "MATCH (s:Skill {name: $name})-[:CATEGORIZED_AS]->(sc:SkillCategory) "
            "RETURN sc.name AS category",
            {"name": skill_name},
        )
        return {
            "skill": skill_name,
            "requires": [r["name"] for r in requires],
            "evolves_into": [e["name"] for e in evolves],
            "category": category[0]["category"] if category else None,
        }

    async def add_skill_relation(
        self, from_skill: str, to_skill: str, relation: str
    ) -> None:
        """スキル間の関係を追加する（REQUIRES または EVOLVES_INTO）."""
        if relation not in ("REQUIRES", "EVOLVES_INTO"):
            raise ValueError(f"無効な関係タイプ: {relation}")
        await self.client.execute_write(
            f"MATCH (a:Skill {{name: $from_skill}}) "
            f"MATCH (b:Skill {{name: $to_skill}}) "
            f"MERGE (a)-[:{relation}]->(b)",
            {"from_skill": from_skill, "to_skill": to_skill},
        )

    # --- 業界・企業関連 ---

    async def get_industry_skills(self, industry: str) -> list[dict[str, Any]]:
        """業界に需要のあるスキル一覧を取得."""
        return await self.client.execute_read(
            "MATCH (c:Company)-[:BELONGS_TO]->(i:Industry {name: $industry}) "
            "MATCH (c)-[d:DEMANDS]->(s:Skill) "
            "RETURN s.name AS skill, avg(d.urgency) AS avg_urgency, sum(d.volume) AS total_volume "
            "ORDER BY avg_urgency DESC",
            {"industry": industry},
        )

    async def add_company(
        self, name: str, industry: str, properties: dict[str, Any] | None = None
    ) -> None:
        """企業ノードを追加し、業界に紐付ける."""
        props = properties or {}
        await self.client.execute_write(
            "MERGE (c:Company {name: $name}) "
            "SET c += $props "
            "WITH c "
            "MATCH (i:Industry {name: $industry}) "
            "MERGE (c)-[:BELONGS_TO]->(i)",
            {"name": name, "industry": industry, "props": props},
        )

    # --- 政策関連 ---

    async def add_policy(
        self, name: str, description: str, affects: list[dict[str, Any]] | None = None
    ) -> None:
        """政策ノードを追加し、影響先を紐付ける."""
        await self.client.execute_write(
            "MERGE (p:Policy {name: $name}) SET p.description = $description",
            {"name": name, "description": description},
        )
        _VALID_TARGET_TYPES = {"Industry", "Skill"}
        for target in (affects or []):
            target_type = target.get("type", "Industry")
            if target_type not in _VALID_TARGET_TYPES:
                raise ValueError(f"無効な影響先タイプ: {target_type}")
            await self.client.execute_write(
                f"MATCH (p:Policy {{name: $policy_name}}) "
                f"MATCH (t:{target_type} {{name: $target_name}}) "
                f"MERGE (p)-[a:AFFECTS]->(t) "
                f"SET a.impact_type = $impact_type, a.magnitude = $magnitude",
                {
                    "policy_name": name,
                    "target_name": target["name"],
                    "impact_type": target.get("impact_type", "neutral"),
                    "magnitude": target.get("magnitude", 0.0),
                },
            )

    # --- 全体取得 ---

    async def get_full_ontology(self) -> dict[str, Any]:
        """知識グラフ全体のサマリーを取得."""
        industries = await self.client.execute_read(
            "MATCH (i:Industry) RETURN i.name AS name, i.label_ja AS label_ja"
        )
        categories = await self.client.execute_read(
            "MATCH (sc:SkillCategory) "
            "OPTIONAL MATCH (s:Skill)-[:CATEGORIZED_AS]->(sc) "
            "RETURN sc.name AS category, sc.label_ja AS label_ja, collect(s.name) AS skills"
        )
        roles = await self.client.execute_read(
            "MATCH (r:Role) RETURN r.name AS name, r.label_ja AS label_ja"
        )
        policies = await self.client.execute_read(
            "MATCH (p:Policy) "
            "OPTIONAL MATCH (p)-[a:AFFECTS]->(t) "
            "RETURN p.name AS name, p.description AS description, "
            "collect({target: t.name, impact_type: a.impact_type, magnitude: a.magnitude}) AS affects"
        )
        return {
            "industries": industries,
            "skill_categories": categories,
            "roles": roles,
            "policies": policies,
        }
